'''
Alphasense reader using the USB-ISS interface. The only real dependency
is on the set_spi_mode and transfer_data functions. This could easily be
replaced with some other layer.

Example:

Suppose that the Alphasense is device /dev/ttyACM0. You can simply run:

python alphasense.py /dev/ttyACM0

USB-ISS Reference:
https://www.robot-electronics.co.uk/htm/usb_iss_tech.htm

Alphasense Reference:
waggle-sensor/waggle/docs/alphasense-opc-n2/
'''
from serial import Serial
from time import sleep
import struct
import sys


def iss_spi_divisor(sck):
    divisor = (6000000 / sck) - 1

    if int(divisor) != divisor:
        raise ValueError('Nonintegral SCK divisor.')

    return int(divisor)


def iss_set_spi_mode(serial, mode, freq):
    serial.write(bytearray([0x5A, 0x02, mode, iss_spi_divisor(freq)]))
    response = serial.read(2)
    if response[0] == 0:
        if response[1] == 0x05:
            raise RuntimeError('USB-ISS: Unknown Command')
        elif response[1] == 0x06:
            raise RuntimeError('USB-ISS: Internal Error 1')
        elif response[1] == 0x07:
            raise RuntimeError('USB-ISS: Internal Error 2')
        else:
            raise RuntimeError('USB-ISS: Undocumented Error')


def iss_spi_transfer_data(serial, data):
    serial.write(bytearray([0x61] + data))
    response = serial.read(1 + len(data))
    if response[0] == 0:
        raise RuntimeError('USB-ISS: Transmission Error')
    return response[1:]


def lininterp(a, b, n):
    assert isinstance(n, int) and n > 1
    return tuple(a + i * (b - a) / (n - 1) for i in range(n))


def decode17(data):
    bincounts = struct.unpack_from('<16B', data, offset=0)
    checksum = struct.unpack_from('<H', data, offset=48)[0]
    mtof = [x / 3 for x in struct.unpack_from('<4B', data, offset=32)]
    sample_flow_rate = struct.unpack_from('<I', data, offset=36)[0]
    pmvalues = struct.unpack_from('<fff', data, offset=50)
    pressure = struct.unpack_from('<I', data, offset=40)[0]
    temperature = pressure / 10.0

    values = {
        'bins': bincounts,
        'mtof': mtof,
        'sample flow rate': sample_flow_rate,
        'pm1': pmvalues[0],
        'pm2.5': pmvalues[1],
        'pm10': pmvalues[2],
        'error': sum(bincounts) & 0xFF != checksum,
    }

    if temperature > 200:
        values['pressure'] = pressure
    else:
        values['temperature'] = temperature

    return values


def unpack_structs(structs, data):
    results = {}

    offset = 0

    for key, fmt in structs:
        values = struct.unpack_from(fmt, data, offset)
        if len(values) == 1:
            results[key] = values[0]
        else:
            results[key] = values
        offset += struct.calcsize(fmt)

    return results


class Alphasense(object):

    bin_units = {
        'bins': 'particle / second',
        'mtof': 'second',
        'sample flow rate': 'sample / second',
        'pm1': 'microgram / meter^3',
        'pm2.5': 'microgram / meter^3',
        'pm10': 'microgram / meter^3',
        'temperature': 'celcius',
        'pressure': 'pascal',
    }

    histogram_data_struct = [
        ('bins', '<16H'),
        ('mtof', '<4B'),
        ('sample flow rate', '<f'),
        ('weather', '<f'),
        ('sampling period', '<I'),
        ('checksum', '<H'),
        ('pm1', '<f'),
        ('pm2.5', '<f'),
        ('pm10', '<f'),
    ]

    config_data_structs = [
        ('bin boundaries', '<16H'),
        ('bin particle volume', '<16f'),
        ('bin particle density', '<16f'),
        ('bin particle weighting', '<16f'),
        ('gain scaling coefficient', '<f'),
        ('sample flow rate', '<f'),
        ('laser dac', '<B'),
        ('fan dac', '<B'),
        ('tof to sfr factor', '<B'),
    ]

    def __init__(self, port):
        self.serial = Serial(port)
        iss_set_spi_mode(self.serial, 0x92, 500000)

    def close(self):
        self.serial.close()

    def transfer(self, data):
        sleep(0.005)
        return iss_spi_transfer_data(self.serial, data)

    def power_on(self, fan=True, laser=True):
        if fan and laser:
            self.transfer([0x03, 0x00])
        elif fan:
            self.transfer([0x03, 0x04])
        elif laser:
            self.transfer([0x03, 0x02])

    def power_off(self, fan=True, laser=True):
        if fan and laser:
            self.transfer([0x03, 0x01])
        elif fan:
            self.transfer([0x03, 0x05])
        elif laser:
            self.transfer([0x03, 0x03])

    def set_laser_power(self, power):
        self.transfer([0x42, 0x01, power])

    def set_fan_power(self, power):
        self.transfer([0x42, 0x00, power])

    def get_firmware_version(self):
        self.transfer([0x3F])
        sleep(0.1)
        return bytearray(self.transfer([0x3F])[0] for i in range(60))

    def get_config_data_raw(self):
        self.transfer([0x3C])
        sleep(0.1)
        return bytearray(self.transfer([0x3C])[0] for i in range(256))

    def get_config_data(self):
        config_data = self.get_config_data_raw()
        return unpack_structs(self.config_data_structs, config_data)

    def ping(self):
        response = self.transfer([0xCF])
        return response[0] == 0xF3

    def get_histogram_raw(self):
        self.transfer([0x30])
        sleep(0.1)
        return bytearray(self.transfer([0x30])[0] for i in range(62))

    def get_histogram(self):
        return decode17(self.get_histogram_binary())

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: {} device-name'.format(sys.argv[0]))
        sys.exit(1)

    alphasense = Alphasense(sys.argv[1])
    sleep(3)

    alphasense.power_on()
    sleep(3)

    config = alphasense.get_config_data()

    try:
        while True:
            rawdata = alphasense.get_histogram_raw()

            data = decode17(rawdata)

            if data['error']:
                alphasense.close()
                raise RuntimeError('Alphasense histogram error.')

            for size, count in zip(config['bin particle volume'], data['bins']):
                print('{: 3.4f} {:>6}'.format(size, count))
            print()

            for pm in ['pm1', 'pm2.5', 'pm10']:
                print('{} {}'.format(pm, data[pm]))
            print()

            sleep(10)
    finally:
        alphasense.close()
