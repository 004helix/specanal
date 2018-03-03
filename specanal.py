#!/usr/bin/env python

import numpy
try:
    import fftw3
    fftw = True
except ImportError:
    fftw = False


class bar:
    def __init__(self, idx, freq1, freq2, l, r):
        self.idx = idx
        self.freq1 = freq1
        self.freq2 = freq2
        self.l = l
        self.r = r
        self.width = 0
        self.weight = 0.0


class specanal:
    def __init__(self, format='s16le', rate=48000, channels=2,
                 lofreq=50, hifreq=16000, bars=20, msec=50,
                 normalize=500):

        self.rate = rate
        self.channels = channels

        if normalize is not None and normalize > 0:
            self.normalize = 2.0 / (1.0 + normalize)
        else:
            self.normalize = 0

        if format not in ('s16be', 's16le'):
            raise Exception('Unsupported format')

        if format == 's16be':
            self.datatype = numpy.dtype('>h')

        if format == 's16le':
            self.datatype = numpy.dtype('<h')

        self.frames = int(rate / (1000.0 / msec))
        self.chunk_size = self.frames * channels * 2

        # pyfftw3
        if fftw:
            z1 = numpy.zeros(self.frames, float)
            z2 = numpy.zeros(self.frames / 2 + 1, complex)
            self.fftw_in = numpy.require(z1, requirements=['ALIGNED'])
            self.fftw_out = numpy.require(z2, requirements=['ALIGNED'])
            self.fftw = fftw3.Plan(self.fftw_in, self.fftw_out,
                                   direction='forward', flags=['measure'])
        # a little bit slower
        else:
            def numpy_fft():
                self.fftw_out = numpy.fft.fft(self.fftw_in)
            self.fftw_in = numpy.zeros(self.frames, float)
            self.fftw = numpy_fft

        # bars
        self.bars = list()
        self.values = numpy.zeros(bars, int)
        self.values_raw = numpy.zeros(bars, float)

        # calculate frequencies
        c = numpy.log10(float(lofreq) / float(hifreq)) / \
            (1.0 / (1.0 + bars) - 1.0)

        for n in range(0, bars):
            power1 = -1.0 * c + (((1.0 + n) / (1.0 + bars)) * c)
            power2 = -1.0 * c + (((2.0 + n) / (1.0 + bars)) * c)
            freq1 = float(hifreq) * numpy.power(10, power1)
            freq2 = float(hifreq) * numpy.power(10, power2)

            l = int(round(freq1 * self.frames / self.rate))
            r = int(round(freq2 * self.frames / self.rate))

            self.bars.append(bar(n, freq1, freq2, l, r))

        # convert to tuple
        self.bars = tuple(self.bars)

        # pushup frequencies
        for n in range(1, bars):
            if self.bars[n].l <= self.bars[n - 1].l:
                self.bars[n].l = self.bars[n - 1].l + 1

            self.bars[n - 1].r = self.bars[n].l - 1

        # calculate width / weight
        for b in self.bars:
            b.width = b.r - b.l + 1
            b.weight = numpy.power(b.freq1, 0.80)

        # normalize (exponential moving average)
        self.ema = 0

    def process(self, data):
        # check data size
        assert len(data) == self.chunk_size

        # convert to numpy array
        data = numpy.frombuffer(data, dtype=self.datatype)

        if self.channels > 1:
            # remix all channels to mono

            # reshape as (L0, R0), (L1, R1), (L2, R2), ...
            data = numpy.reshape(data, (self.frames, self.channels))

            # convert to float and summarize channels
            data = data.astype(float).sum(axis=1)

            # normalize -1.0...1.0
            self.fftw_in[:] = numpy.divide(data, 32768 * self.channels)

        else:
            # already mono input
            data = data.astype(float)

            # normalize -1.0...1.0
            self.fftw_in[:] = numpy.divide(data, 32768)

        # run DFT
        self.fftw()

        # calculate the absolute value for each complex value in result
        data = numpy.absolute(self.fftw_out)

        # convert result into bar raw values
        for bar in self.bars:
            self.values_raw[bar.idx] = bar.weight * \
                numpy.sum(data[bar.l:bar.r + 1]) / bar.width

        # normalize bars
        if self.normalize > 0:
            avg = self.values_raw.sum() / len(self.bars)

            if avg > 0:
                if self.ema > 0:
                    self.ema = self.normalize * avg + \
                        (1.0 - self.normalize) * self.ema
                else:
                    self.ema = avg

                k = 12000.0 / self.ema if self.ema > 1 else 0
                v = numpy.multiply(self.values_raw, k).astype(int)
                self.values = numpy.clip(v, 0, 65535)
            else:
                self.values = numpy.zeros(len(self.bars), int)


if __name__ == '__main__':
    import sys

    bars = specanal('s16le', 48000, 2, 50, 14000)
    size = bars.frames * bars.channels * 2

    for bar in bars.bars:
        print('%02d %f -> %f' % (bar.idx, bar.freq1, bar.freq2))

    while True:
        data = sys.stdin.read(size)
        if len(data) != size:
            break

        bars.process(data)

        line = ['|']
        for cutoff in (61440, 57344, 53248, 49152, 45056, 40960, 36864,
                       32768, 28672, 24576, 20480, 16384, 12288, 8192, 4096):
            for val in bars.values:
                line.append('## ' if val > cutoff else '   ')
            line.append('|\n|')

        for bar in bars.bars:
            line.append('%02d ' % (bar.idx,))

        line.append('|\n')

        sys.stdout.write(''.join(line))
