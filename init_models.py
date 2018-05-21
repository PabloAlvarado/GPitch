from gpflow.kernels import Matern52, Matern32, Matern12
from gpitch.kernels import Matern32sm, MercerCosMix
from gpitch.methods import find_ideal_f0, init_cparam
import numpy as np
import gpflow

def init_iv(x, num_sources, nivps_a, nivps_c, fs=16000):
    """
    Initialize inducing variables
    :param x: time vector
    :param fs: sample frequency
    :param nivps_a: number inducing variables per second for activation
    :param nivps_c: number inducing variables per second for component
    """
    dec_a = fs/nivps_a
    dec_c = fs/nivps_c
    za = []
    zc = []
    for i in range(num_sources):
        za.append(np.vstack([x[::dec_a].copy(), x[-1].copy()]))  # location ind v act
        zc.append(np.vstack([x[::dec_c].copy(), x[-1].copy()]))  # location ind v comp
    z = [za, zc]
    return z

def init_kernel_training(y, list_files, fs=16000, maxh=25):
    num_pitches = len(list_files)
    if0 = find_ideal_f0(list_files)  # ideal frequency for each pitch
    iparam = []  # initilize component kernel parameters for each pitch model
    kern_act = []
    kern_com = []
    for i in range(num_pitches):
        iparam.append(init_cparam(y[i], fs=fs, maxh=maxh, ideal_f0=if0[i])) # init component kern params

        kern_act.append(Matern12(1, lengthscales=1., variance=3.5))
        kern_com.append(Matern32sm(1, num_partials=len(iparam[i][1]), lengthscales=1., variances=iparam[i][1],
                                   frequencies=iparam[i][0]))
        kern_com[i].vars_n_freqs_fixed()

    kern = [kern_act, kern_com]
    return kern, iparam # list of all required kernels and its initial parameters

def init_kernel_with_trained_models(m, option_two=False):
    kern_act = []
    kern_com = []
    num_sources = len(m)
    for i in range(num_sources):
        num_p = m[i].kern_com[0].num_partials
        kern_act.append(Matern12(1))
        kern_com.append(Matern32sm(1, num_partials=num_p))
                
        kern_act[i].fixed = True
        kern_com[i].fixed = True
        kern_com[i].vars_n_freqs_fixed(fix_var=True, fix_freq=False)
        
        if option_two:
            kern_act[i].lengthscales = 0.5
            kern_act[i].variance = 4.0
            kern_com[i].lengthscales = 1.0
        else:
            kern_act[i].lengthscales = m[i].kern_act[0].lengthscales.value.copy()
            kern_act[i].variance = m[i].kern_act[0].variance.value.copy()
            kern_com[i].lengthscales = m[i].kern_com[0].lengthscales.value.copy()
        
        kern_act[i].fixed = False
        kern_com[i].lengthscales.fixed = False
        
        for j in range(num_p):
            kern_com[i].frequency[j] = m[i].kern_com[0].frequency[j].value.copy()
            kern_com[i].variance[j] = m[i].kern_com[0].variance[j].value.copy()
    return [kern_act, kern_com]

def reset_model(m, x, y, nivps, m_trained, option_two=False):
    num_sources = len(m.za)
    m.x = x.copy()
    m.y = y.copy()
    m.likelihood.variance = 1.    
    new_z = init_iv(x, num_sources, nivps[0], nivps[1])
    for i in range(num_sources):
        m.za[i] = new_z[0][i].copy()
        m.zc[i] = new_z[1][i].copy()
        
        m.q_mu_act[i] = np.zeros((new_z[0][i].shape[0], 1))
        m.q_mu_com[i] = np.zeros((new_z[1][i].shape[0], 1))
        
        m.q_sqrt_act[i] = np.array([np.eye(new_z[0][i].shape[0]) for _ in range(1)]).swapaxes(0, 2)
        m.q_sqrt_com[i] = np.array([np.eye(new_z[1][i].shape[0]) for _ in range(1)]).swapaxes(0, 2)
        
        
        if option_two:
            m.kern_act[i].lengthscales = 0.5
            m.kern_act[i].variance = 4.0
            m.kern_com[i].lengthscales = 1.0
        else:    
            m.kern_act[i].lengthscales = m_trained[i].kern_act[0].lengthscales.value.copy()
            m.kern_act[i].variance = m_trained[i].kern_act[0].variance.value.copy()
            m.kern_com[i].lengthscales = m_trained[i].kern_com[0].lengthscales.value.copy()
        
        num_p = m.kern_com[i].num_partials
        for j in range(num_p):
            m.kern_com[i].frequency[j] = m_trained[i].kern_com[0].frequency[j].value.copy()
            m.kern_com[i].variance[j] = m_trained[i].kern_com[0].variance[j].value.copy()
       
    
def get_features(f, s, f_centers, nfpc):
    """Get kernel features (parameters) from FFT of training data"""
    var_l = []
    freq_l = []
    for i in range(f_centers.size):
        idx =  np.argmin(np.abs(f - f_centers[i]))
        if nfpc == 1:
            freq_l.append(f[idx: idx + 1])
            var_l.append(s[idx: idx + 1])
        else:
            freq_l.append(f[idx -nfpc//2: idx + nfpc//2])
            var_l.append(s[idx -nfpc//2: idx + nfpc//2])
    frequency = np.asarray(freq_l).reshape(-1, 1)
    energy = np.asarray(var_l).reshape(-1, 1)
    return frequency, energy


def init_kern(num_pitches, energy, frequency):
    """Initialize kernels for activations and components"""
    k_act, k_com = [], []
    k_com_a, k_com_b = [], []
    for i in range(num_pitches):
        k_act.append( Matern12(1, lengthscales=1., variance=3.5) )

        k_com_a.append( Matern52(1, lengthscales=0.25, variance=1.0) )
        k_com_a[i].variance.fixed = True
        k_com_a[i].lengthscales.transform = gpflow.transforms.Logistic(0., 0.5)
        k_com_b.append( MercerCosMix(input_dim=1, energy=energy[i].copy(),
                                                    frequency=frequency[i].copy(), variance=0.25))
        k_com_b[i].fixed = True
        k_com.append( k_com_a[i]*k_com_b[i] )
    kern = [k_act, k_com]
    return kern
#
