#!/usr/bin/env python

import numpy


class drygalki:
    def __init__(self, format='s16le', rate=48000, channels=2,
                 points=50, msec=50):

        self.rate = rate
        self.channels = channels

        if format not in ('s16be', 's16le'):
            raise Exception('Unsupported format')

        if format == 's16be':
            self.datatype = numpy.dtype('>h')

        if format == 's16le':
            self.datatype = numpy.dtype('<h')

        self.frames = int(rate / (1000.0 / msec))
        self.chunk_size = self.frames * channels * 2

        if self.frames % points:
            raise Exception('frames % points != 0')

        self.points = points
        self.pwidth = self.frames / points

    def convert(self, raw_data):
        # check data size
        assert len(raw_data) == self.chunk_size

        # convert to numpy array
        data = numpy.frombuffer(raw_data, dtype=self.datatype)

        if self.channels > 1:
            # remix all channels to mono

            # reshape as (L0, R0), (L1, R1), (L2, R2), ...
            data = numpy.reshape(data, (self.frames, self.channels))

            # convert to float and summarize channels
            data = data.astype(float).sum(axis=1)

            # normalize -1.0...1.0
            return numpy.divide(data, 32768 * self.channels)

        else:
            # already mono input
            data = data.astype(float)

            # normalize -1.0...1.0
            return numpy.divide(data, 32768)

    def process(self, norm_data):
        # check normalized data size
        assert len(norm_data) == self.frames

        # summarize all points
        data = numpy.reshape(norm_data, (self.points, self.pwidth)).sum(axis=1)

        # save points
        self.values = numpy.divide(data, self.pwidth)

if __name__ == '__main__':
    d = drygalki('s16le')
