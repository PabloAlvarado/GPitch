import numpy as np
import tensorflow as tf
import gpflow
from scipy.io import wavfile as wav
from scipy.fftpack import fft, ifft
import matplotlib
server = True # define if running code on server
if server:
   matplotlib.use('agg')
from matplotlib import pyplot as plt
import sys
sys.path.append('../../')
import gpitch

gpitch.amtgp.init_settings(visible_device='1', interactive=True) #  configure gpu usage and plotting
N = 32000 # numer of data points to load
fs, y = gpitch.amtgp.wavread('../../../datasets/60_1-down.wav', start=5000, N=N) # load two seconds of data
x = np.linspace(0, (N-1.)/fs, N).reshape(-1, 1)
ws = N # window size (in this case the complete data)
dsamp = 160 #  downsample rate for inducing points vector

m = gpitch.modpdet.ModPDet(x=x, y=y, fs=fs, ws=ws, jump=dsamp)
m.model.whiten = False
m.model.kern1.fixed = True
m.model.kern2.fixed = False # activation kernel
maxiter = 100
restarts = 1000
init_hyper, learnt_hyper, mse = m.optimize_restart(maxiter=maxiter, restarts=restarts)
m.model.kern2.lengthscales = learnt_hyper[0].mean()
m.model.kern2.variance = learnt_hyper[1].mean()
m.model.kern1.fixed = True
m.model.kern2.fixed = False
m.optimize(disp=0, maxiter=maxiter)

plt.rcParams['figure.figsize'] = (18, 18)  # set plot size
zoom_limits = [x.max()/2, x.max()/2 + 0.01*x.max()]
fig, fig_array = m.plot_results(zoom_limits)
#plt.savefig('../figures/demo_modgp_maps.pdf')
plt.savefig('../../results/figures/demo_modgp_maps.png')

f, axs = plt.subplots(1, 2, figsize=(8, 4), tight_layout=True, sharex=True, sharey=True)
axs[0].plot(init_hyper[0], init_hyper[1], 'k.', ms=10, alpha=0.25)
axs[0].set_xlabel('initial lengthscale')
axs[0].set_ylabel('initial variance')
axs[1].plot(learnt_hyper[0], learnt_hyper[1], 'k.', ms=10, alpha=0.25)
axs[1].plot(m.model.kern2.lengthscales.value, m.model.kern2.variance.value, 'rx', mew=2)
axs[1].set_xlabel('learnt lengthscale')
axs[1].set_ylabel('learnt variance')
#plt.savefig('../figures/demo_modgp_maps_hyperparams.pdf')
plt.savefig('../../results/figures/demo_modgp_maps_hyperparams.png')





























#