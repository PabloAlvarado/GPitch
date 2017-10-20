import time, sys, os
sys.path.append('../../')
import matplotlib
if True: matplotlib.use('agg') # define if running code on server (True)
from matplotlib import pyplot as plt
import numpy as np
import tensorflow as tf
import gpflow, gpitch
from gpitch.amtgp import logistic
reload(gpitch)


#np.random.seed(29)
gpitch.amtgp.init_settings(visible_device=sys.argv[1], interactive=True) #  confi gpu usage, plot
fs = 16e3  # generate synthetic data
N = 1600  # number of samples
x = np.linspace(0, (N-1.)/fs, N).reshape(-1, 1)  # time
noise_var = 1.e-3  # noise variance
pitch1 = 440.00  # Hertz, A4 (La)
pitch2 = 659.25  # Hertz, E5 (Mi)
kenv1 = gpflow.kernels.Matern32(input_dim=1, lengthscales=0.01, variance=10.)
kenv2 = gpflow.kernels.Matern32(input_dim=1, lengthscales=0.005, variance=10.)
kper1 = gpflow.kernels.PeriodicKernel(input_dim=1, lengthscales=0.25,
                                      variance=np.sqrt(0.5), period=1./pitch1)
kper2 = gpflow.kernels.PeriodicKernel(input_dim=1, lengthscales=0.25,
                                      variance=np.sqrt(0.5), period=1./pitch2)
Kenv1 = kenv1.compute_K_symm(x)
Kenv2 = kenv2.compute_K_symm(x)
Kper1 = kper1.compute_K_symm(x)
Kper2 = kper2.compute_K_symm(x)
f1 = np.random.multivariate_normal(np.zeros(x.shape[0]), Kper1).reshape(-1, 1)
f2 = np.random.multivariate_normal(np.zeros(x.shape[0]), Kper2).reshape(-1, 1)
f1 /= np.max(np.abs(f1))
f2 /= np.max(np.abs(f2))
g1 = np.random.multivariate_normal(np.zeros(x.shape[0]), Kenv1).reshape(-1, 1)
g2 = np.random.multivariate_normal(np.zeros(x.shape[0]), Kenv2).reshape(-1, 1)
source1 = gpitch.amtgp.logistic(g1)*f1
source2 = gpitch.amtgp.logistic(g2)*f2
mean = source1 + source2
y = mean + np.random.randn(*mean.shape) * np.sqrt(noise_var)

dec = 10
aux_list = np.asarray([1., 2.]).reshape(-1,)
params = {
          'l_act1' : 1.,
          's_act1' : 1.,

          'l_act2' : 1.,
          's_act2' : 1.,

          'l_com1' : aux_list,
          's_com1' : aux_list,
          'f_com1' : aux_list,

          'l_com2' : aux_list,
          's_com2' : aux_list,
          'f_com2' : aux_list
         }

# define kernels
kern_com1 = gpitch.amtgp.Matern12CosineMix(variance=params['s_com1'],
                                           lengthscale=params['l_com1'],
                                           period=1./params['f_com1'],
                                           Nh=params['s_com1'].size)

kern_com2 = gpitch.amtgp.Matern12CosineMix(variance=params['s_com2'],
                                           lengthscale=params['l_com2'],
                                           period=1./params['f_com2'],
                                           Nh=params['s_com2'].size)

kern_act1 = gpflow.kernels.Matern32(input_dim=1, lengthscales=params['l_act1'],
                                    variance=params['s_act1'])

kern_act2 = gpflow.kernels.Matern32(input_dim=1, lengthscales=params['l_act2'],
                                    variance=params['s_act2'])

kc = [kper1, kper2]
ka = [kenv1, kenv2]
ws = N # winsow size in samples
m = gpitch.loopdet.LooPDet(x=x, y=y, kern_comps=kc, kern_acts=ka, ws=ws, dec=dec, whiten=True)
m.optimize_windowed(disp=1, maxiter=100)
m.plot_results()
plt.tight_layout()
plt.savefig('../../../results/figures/demos/demo_loogp_toy_new.png')































#