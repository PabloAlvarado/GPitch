import numpy as np
import pickle
import h5py
import gpflow
import gpitch
import matplotlib.pyplot as plt
from scipy import fftpack


class Audio:
    def __init__(self, path=None, filename=None, frames=-1, start=0, scaled=True, window_size=None):

        if path is None:
            self.name = 'unnamed'
            self.fs = 44100
            self.x = np.linspace(0., (self.fs - 1.)/self.fs,  self.fs).reshape(-1, 1)
            self.y = np.cos(2*np.pi*self.x*440.)

        else:
            self.name = filename
            self.x, self.y, self.fs = gpitch.readaudio(fname=path + filename, frames=frames, start=start, scaled=scaled)

        if window_size is None:
            window_size = self.x.size
        self.wsize = window_size
        self.X, self.Y = gpitch.segmented(x=self.x, y=self.y, window_size=window_size)


class AMT:
    """
    Automatic music transcription class
    """

    def __init__(self, pitches, nsec=1, test_filename=None, window_size=4410, run_on_server=True, gpu='0'):

        self.piano_roll = 1
        self.pitches = pitches
        self.train_data = [None]
        self.test_data = Audio()
        self.params = [[], [], []]
        self.kern_sampled = [None]
        self.inducing = [None]
        self.kern_pitches = [None]
        self.model = None
        self.sampled_cov = [None]


        self.mean = []
        self.var = []

        self.var1 = []
        self.var2 = []
        self.var3 = []
        self.var4 = []
        self.var5 = []
        self.var6 = []
        self.var7 = []
        self.var8 = []
        self.var9 = []
        self.var10 = []

        # init session
        self.sess, self.path = gpitch.init_settings(visible_device=gpu, run_on_server=run_on_server)

        self.kernel_path = 'c4dm-04/alvarado/results/sampling_covariance/maps/rectified/'

        if run_on_server:
            self.train_path = "c4dm-01/MAPS_original/AkPnBcht/ISOL/NO/"
            self.test_path = "c4dm-01/MAPS_original/AkPnBcht/MUS/"
        else:
            self.train_path = "media/pa/TOSHIBA EXT/Datasets/MAPS/AkPnBcht/ISOL/NO/"
            self.test_path = "media/pa/TOSHIBA EXT/Datasets/MAPS/AkPnBcht/MUS/"

        self.load_train(pitches=pitches)

        if test_filename is not None:
            self.load_test(filename=test_filename, start=0, frames=nsec*44100, window_size=window_size)

    def load_train(self, pitches, train_data_path=None):

        if train_data_path is not None:
            self.train_path = train_data_path

        path = self.path + self.train_path
        lfiles = gpitch.methods.load_filenames(directory=path, pattern='F', pitches=pitches)
        nfiles = len(lfiles)
        data = []

        for i in range(nfiles):
            if lfiles[i].find("S1") is not -1:
                start = 30000
            else:
                start = 20000
            data.append(Audio(path=path, filename=lfiles[i], start=start, frames=88200))
        self.train_data = data

    def load_test(self, filename, window_size, start, frames, train_data_path=None):
        if train_data_path is not None:
            self.test_path = train_data_path
        path = self.path + self.test_path
        self.test_data = Audio(path=path, filename=filename, start=start, frames=frames, window_size=window_size)

        self.piano_roll = 1.

    def plot_traindata(self, figsize=None, axis_off=True):
        nfiles = len(self.train_data)

        if nfiles <= 4:
            ncols = nfiles
        else:
            ncols = 4

        nrows = int(np.ceil(nfiles/4.))

        if figsize is None:
            figsize = (16, 2*nrows)

        plt.figure(figsize=figsize)
        for i in range(nfiles):
            plt.subplot(nrows, ncols, i+1)
            plt.plot(self.train_data[i].x, self.train_data[i].y)
            plt.legend([self.train_data[i].name[18:-13]])
            if axis_off:
                plt.axis("off")
        plt.suptitle("train data")

    def plot_testdata(self, figsize=(16, 2), axis_off=False):
        plt.figure(figsize=figsize)
        plt.plot(self.test_data.x, self.test_data.y)
        plt.legend([self.test_data.name])
        plt.title("test data")
        if axis_off:
            plt.axis("off")

    def plot_kernel(self, figsize=None, axis=False):
        nfiles = len(self.train_data)

        if nfiles <= 2:
            ncols = nfiles
        else:
            ncols = 2

        nrows = int(np.ceil(nfiles / 2.))
        x0 = np.array(0.).reshape(-1, 1)

        if figsize is None:
            figsize = (16, 2*nrows)

        plt.figure(figsize=figsize)
        for i in range(nfiles):
            plt.subplot(nrows, ncols, i + 1)

            plt.plot(self.kern_sampled[0][i], self.kern_sampled[1][i])
            plt.plot(self.kern_sampled[0][i], self.kern_pitches[i].compute_K(self.kern_sampled[0][i], x0))
            # x1 = np.linspace(0, (441-1.)/44100, 441).reshape(-1, 1)
            # plt.plot(self.kern_pitches[i].compute_K(x1, x0))
            plt.title(self.train_data[i].name[18:-13])
            plt.legend(['sampled kernel', 'approximate kernel'])
            if axis is not True:
                plt.axis("off")
        plt.suptitle("sampled kernels")

    def load_kernel(self):
        path = self.path + self.kernel_path
        param_filename = gpitch.load_filenames(directory=path, pattern='params', pitches=self.pitches, ext='.p')

        self.params = [[], [], []]
        self.kern_sampled = [[], []]

        for i in range(len(self.pitches)):
            aux_param = pickle.load(open(path + param_filename[i], "rb"))
            self.params[0].append(aux_param[0])
            self.params[1].append(aux_param[1])
            self.params[2].append(aux_param[2])

            self.kern_sampled[0].append(aux_param[3])
            self.kern_sampled[1].append(aux_param[4])

    def init_kernel(self, covsize=441, num_sam=10000, max_par=20, train=False, save=False, load=False):

        nfiles = len(self.train_data)
        self.params = [[], [], []]
        skern, xkern = nfiles * [np.zeros((1, 1))], nfiles * [None]

        if train:
            scov, samples = nfiles * [None], nfiles * [None]
            self.sampled_cov = nfiles * [None]

            for i in range(nfiles):

                # sample cov matrix
                self.sampled_cov[i], skern[i], samples[i] = gpitch.samplecov.get_cov(self.train_data[i].y,
                                                                                     num_sam=num_sam, size=covsize)

                # approx kernel
                params = gpitch.kernelfit.fit(kern=skern[i], audio=self.train_data[i].y,
                                              file_name=self.train_data[i].name, max_par=max_par)[0]
                self.params[0].append(params[0])  # lengthscale
                self.params[1].append(params[1])  # variances
                self.params[2].append(params[2])   # frequencies

                xkern[i] = np.linspace(0., (covsize - 1.) / self.train_data[i].fs, covsize).reshape(-1, 1)
            self.kern_sampled = [xkern, skern]

            if save:
                self.save()

        elif load:
            self.load_kernel()  # load already learned parameters

        else:
            # init kernels with fft of data
            for i in range(nfiles):
                f0 = gpitch.find_ideal_f0([self.train_data[i].name])[0]

                params = gpitch.init_cparam(y=self.train_data[i].y.copy(),
                                            fs=self.train_data[i].fs,
                                            maxh=max_par,
                                            ideal_f0=f0)

                self.params[0].append(np.array(0.05))  # lengthscale
                self.params[1].append(params[1])  # variances
                self.params[2].append(params[0])  # frequencies

                skern[i] = fftpack.ifft(np.abs(fftpack.fft(self.train_data[i].y.copy().reshape(-1, ))))[0:covsize]
                skern[i] /= np.max(skern[i])
                xkern[i] = np.linspace(0., (covsize - 1.) / self.train_data[i].fs, covsize).reshape(-1, 1)
            self.kern_sampled = [xkern, skern]

        # init kernel specific pitch
        self.kern_pitches = gpitch.init_kernels.init_kern_com(num_pitches=len(self.train_data),
                                                              lengthscale=self.params[0],
                                                              energy=self.params[1],
                                                              frequency=self.params[2],
                                                              len_fixed=False)

    def init_inducing(self):
        nwin = len(self.test_data.X)
        u = nwin * [None]
        z = nwin * [None]

        for i in range(nwin):
            a, b = gpitch.init_liv(x=self.test_data.X[i], y=self.test_data.Y[i], num_sources=1)
            z[i] = a[0][0]
            u[i] = b
        self.inducing = [z, u]

    def init_model(self):
        """Hi"""
        self.init_inducing()  # init inducing points

        # init model kernel
        kern_model = np.sum(self.kern_pitches)

        # init gp model
        x_init = self.test_data.X[0].copy()
        y_init = self.test_data.Y[0].copy()
        z_init = self.inducing[0][0].copy()
        self.model = gpflow.sgpr.SGPR(X=x_init, Y=y_init, kern=kern_model, Z=z_init)

    def reset_model(self, x, y, z):
        self.model.X = x.copy()
        self.model.Y = 20.*y.copy()
        self.model.Z = z.copy()
        self.model.likelihood.variance = 1.

        init_var = 0.00001
        self.model.kern.prod_1.matern12.variance = init_var
        self.model.kern.prod_2.matern12.variance = init_var
        self.model.kern.prod_3.matern12.variance = init_var
        self.model.kern.prod_4.matern12.variance = init_var
        self.model.kern.prod_5.matern12.variance = init_var
        self.model.kern.prod_6.matern12.variance = init_var
        self.model.kern.prod_7.matern12.variance = init_var
        self.model.kern.prod_8.matern12.variance = init_var
        self.model.kern.prod_9.matern12.variance = init_var
        self.model.kern.prod_10.matern12.variance = init_var

        self.model.kern.prod_1.matern12.lengthscales = self.params[0][0].copy()
        self.model.kern.prod_2.matern12.lengthscales = self.params[0][1].copy()
        self.model.kern.prod_3.matern12.lengthscales = self.params[0][2].copy()
        self.model.kern.prod_4.matern12.lengthscales = self.params[0][3].copy()
        self.model.kern.prod_5.matern12.lengthscales = self.params[0][4].copy()
        self.model.kern.prod_6.matern12.lengthscales = self.params[0][5].copy()
        self.model.kern.prod_7.matern12.lengthscales = self.params[0][6].copy()
        self.model.kern.prod_8.matern12.lengthscales = self.params[0][7].copy()
        self.model.kern.prod_9.matern12.lengthscales = self.params[0][8].copy()
        self.model.kern.prod_10.matern12.lengthscales = self.params[0][9].copy()

    def optimize(self, maxiter, disp=1, nwin=None):

        self.mean = []
        self.var = []

        if nwin is None:
            nwin = len(self.test_data.Y)

        for i in range(nwin):
            # reset model

            self.reset_model(x=self.test_data.X[i],
                             y=self.test_data.Y[i],
                             z=self.inducing[0][i])

            # optimize window
            self.model.optimize(disp=disp, maxiter=maxiter)

            # save learned params
            self.var1.append(self.model.kern.prod_1.matern12.variance.value.copy())
            self.var2.append(self.model.kern.prod_2.matern12.variance.value.copy())
            self.var3.append(self.model.kern.prod_3.matern12.variance.value.copy())
            self.var4.append(self.model.kern.prod_4.matern12.variance.value.copy())
            self.var5.append(self.model.kern.prod_5.matern12.variance.value.copy())
            self.var6.append(self.model.kern.prod_6.matern12.variance.value.copy())
            self.var7.append(self.model.kern.prod_7.matern12.variance.value.copy())
            self.var8.append(self.model.kern.prod_8.matern12.variance.value.copy())
            self.var9.append(self.model.kern.prod_9.matern12.variance.value.copy())
            self.var10.append(self.model.kern.prod_10.matern12.variance.value.copy())

            # predict
            mean, var = self.model.predict_f(self.test_data.X[i].copy())
            self.mean.append(mean)
            self.var.append(var)

    def save(self):
        # save results
        for i in range(len(self.pitches)):
            auxname = self.train_data[i].name.strip('.wav')
            fname_cov = auxname + '_cov_matrix'
            fname_param = self.path + self.kernel_path + auxname + '_kern_params'

            with h5py.File(self.path + self.kernel_path + fname_cov + '.h5', 'w') as hf:
                hf.create_dataset(fname_cov, data=self.sampled_cov[i])

            pickle.dump([self.params[0][i],
                         self.params[1][i],
                         self.params[2][i],
                         self.kern_sampled[0][i],
                         self.kern_sampled[1][i]],
                        open(fname_param + ".p", "wb"))

    # def predict(self, xnew=None):
    #     if xnew is None:
    #         mean = np.asarray(self.mean).reshape(-1, 1)
    #         var = np.asarray(self.var).reshape(-1, 1)
    #     else:
    #         mean, var = self.model.predict_f(xnew)
    #
    #     return mean, var
            #
            #
