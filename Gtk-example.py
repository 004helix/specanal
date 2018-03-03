#!/usr/bin/python

# run:
#
# pacat -r -d <name|idx> --format=s16le --channels=2 --rate=48000 | ./Gtk-example.py
#             <name|idx> - name or index of pulseaudio source

import os
import sys
import gtk
import glib
import numpy
import cairo
import specanal
import drygalki


class Example(gtk.Window):
    def __init__(self):
        super(Example, self).__init__()

        self.set_title("specanal / drygalki")
        self.resize(300, 200)
        self.set_position(gtk.WIN_POS_CENTER)

        self.connect("destroy", gtk.main_quit)

        self.darea = gtk.DrawingArea()
        self.darea.connect("expose-event", self.expose)
        self.add(self.darea)

        stdin = glib.IOChannel(sys.stdin.fileno())
        stdin.add_watch(glib.IO_IN | glib.IO_HUP,
                        self.update, priority=glib.PRIORITY_HIGH)

        # init spectrum analyzer:
        #   input:
        #     s16le 2ch 48000Hz
        #   output:
        #     50Hz <-> 16kHz
        #     total 28 bars
        #   chunk length:
        #     50ms
        self.sa = specanal.specanal('s16le', 48000, 2, 50, 16000, 28, 50)
        self.sa_sfc = cairo.ImageSurface(cairo.FORMAT_RGB24, 200, 64)
        self.sa_ctx = cairo.Context(self.sa_sfc)

        # init drygalki:
        #   input:
        #     s16le 2ch 48000Hz
        #   output:
        #     100 points
        #   chunk length:
        #     50ms
        self.dg = drygalki.drygalki('s16le', 48000, 2, 100, 50)
        self.dg_sfc = cairo.ImageSurface(cairo.FORMAT_RGB24, 100, 20)
        self.dg_ctx = cairo.Context(self.dg_sfc)
        self.dg_ctx.set_line_width(1)

        self.data = ''
        self.show_all()

    def update(self, stdin, condition):
        self.data += os.read(sys.stdin.fileno(), 9600)
        if len(self.data) < 9600:
            return True

        chunk = self.data[0:9600]
        self.data = self.data[9600:]

        ctx = self.darea.window.cairo_create()

        # specanal process
        self.sa.process(chunk)

        # clear specanal surface
        self.sa_ctx.set_source_rgb(0, 0, 0)
        self.sa_ctx.paint()

        # draw specanal
        self.sa_ctx.set_source_rgb(1, 1, 1)

        v = numpy.multiply(self.sa.values, 62.0 / 65536.0)
        v = numpy.add(v.astype(int), 1)

        x = 2
        for f in v:
            self.sa_ctx.rectangle(x, 63 - f, 6, f)
            self.sa_ctx.fill()
            x += 7

        # drygalki process
        self.dg.process(chunk)

        # clear drygalki surface
        self.dg_ctx.set_source_rgb(0, 0, 0)
        self.dg_ctx.paint()

        # draw drygalki
        self.dg_ctx.set_source_rgb(1, 1, 1)

        x = 100
        for c in numpy.clip(numpy.multiply(self.dg.values, 20.0), -9.0, 9.0):
            y = 10.5 + c
            if x == 100:
                self.dg_ctx.move_to(x, y)
            else:
                self.dg_ctx.line_to(x - 0.5, y)
            x -= 1

        self.dg_ctx.line_to(x, y)
        self.dg_ctx.stroke()

        # copy both widgets to main surface
        x = self.allocation.width / 2 - 100
        y = self.allocation.height / 2 - 50

        ctx.set_source_surface(self.sa_sfc, x, y)
        ctx.rectangle(x, y, 200, 64)
        ctx.fill()

        x += 50
        y += 70
        ctx.set_source_surface(self.dg_sfc, x, y)
        ctx.rectangle(x, y, 100, 50)
        ctx.fill()

        return True

    def expose(self, widget, event):
        ctx = widget.window.cairo_create()
        ctx.set_source_rgb(0.2, 0.2, 0.2)
        ctx.paint()


if __name__ == '__main__':
    Example()
    gtk.main()
