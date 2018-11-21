import numpy as np
from gpitch import readaudio, segmented
from gpitch import window_overlap


class Audio:
    def __init__(self, path=None, filename=None, frames=-1, start=0, scaled=False, window_size=None, overlap=True):

        self.path = path

        if path is None:
            self.name = 'unnamed'
            self.fs = 16000
            self.x = np.linspace(0., (self.fs - 1.)/self.fs,  self.fs).reshape(-1, 1)
            self.y = np.cos(2*np.pi*self.x*440.)

        else:
            self.read(filename=filename, frames=frames, start=start, scaled=scaled)

        if window_size is None:
            window_size = self.x.size
        self.wsize = window_size

        self.X, self.Y = self.windowed(overlap)

    def read(self, filename, frames=-1, start=0, scaled=False):
        self.name = filename
        self.x, self.y, self.fs = readaudio(fname=self.path + filename, frames=frames, start=start, scaled=scaled)

    def windowed(self, overlap):
        if overlap:
            X, Y = window_overlap.windowed(x=self.x, y=self.y, ws=self.wsize)
        else:
            X, Y = segmented(x=self.x, y=self.y, window_size=self.wsize)

        self.X, self.Y = X, Y
        return X, Y
