import numpy as np

from alias.src.wave_function import (
    wave_function_array,
    wave_function,
    d_wave_function_array,
    d_wave_function,
    dd_wave_function_array,
    dd_wave_function,
    vcheck,
    wave_arrays,
    wave_indices
)


def xi(x, y, coeff, qm, qu, dim):
    """
    Function returning position of intrinsic surface at position (x,y)

    Parameters
    ----------
    x:  float, array_like; shape=(nmol)
        Coordinate in x dimension
    y:  float, array_like; shape=(nmol)
        Coordinate in y dimension
    coeff:	float, array_like; shape=(n_waves**2)
        Optimised surface coefficients
    qm:  int
        Maximum number of wave frequencies in Fouier Sum representing
        intrinsic surface
    qu:  int
        Upper limit of wave frequencies in Fouier Sum representing
        intrinsic surface
    dim:  float, array_like; shape=(3)
        XYZ dimensions of simulation cell

    Returns
    -------
    xi_z:  float, array_like; shape=(nmol)
        Positions of intrinsic surface in z dimension

    """

    if np.isscalar(x):
        u_array, v_array = wave_arrays(qm)
        indices = wave_indices(qu, u_array, v_array)

        wave_x = wave_function_array(x, u_array[indices], dim[0])
        wave_y = wave_function_array(y, v_array[indices], dim[1])
        xi_z = np.sum(wave_x * wave_y * coeff[indices])
    else:
        xi_z = np.zeros(x.shape)
        for u in range(-qu, qu+1):
            for v in range(-qu, qu+1):
                j = (2 * qm + 1) * (u + qm) + (v + qm)
                wave_x = wave_function(x, u, dim[0])
                wave_y = wave_function(y, v, dim[1])
                xi_z += wave_x * wave_y * coeff[j]

    return xi_z


def dxy_dxi(x, y, coeff, qm, qu, dim):
    """
    Function returning derivatives of intrinsic surface at
    position (x,y) wrt x and y

    Parameters
    ----------
    x:  float
        Coordinate in x dimension
    y:  float
        Coordinate in y dimension
    coeff:	float, array_like; shape=(n_waves**2)
        Optimised surface coefficients
    qm:  int
        Maximum number of wave frequencies in Fourier Sum
        representing intrinsic surface
    qu:  int
        Upper limit of wave frequencies in Fourier Sum
        representing intrinsic surface
    dim:  float, array_like; shape=(3)
        XYZ dimensions of simulation cell

    Returns
    -------
    dx_dxi:  float
        Derivative of intrinsic surface in x dimension
    dy_dxi:  float
        Derivative of intrinsic surface in y dimension

    """

    if np.isscalar(x):
        u_array, v_array = wave_arrays(qm)
        indices = wave_indices(qu, u_array, v_array)

        wave_x = wave_function_array(x, u_array[indices], dim[0])
        wave_y = wave_function_array(y, v_array[indices], dim[1])
        wave_dx = d_wave_function_array(x, u_array[indices], dim[0])
        wave_dy = d_wave_function_array(y, v_array[indices], dim[1])

        dx_dxi = np.sum(wave_dx * wave_y * coeff[indices])
        dy_dxi = np.sum(wave_x * wave_dy * coeff[indices])

    else:
        dx_dxi = np.zeros(x.shape)
        dy_dxi = np.zeros(x.shape)
        for u in range(-qu, qu+1):
            for v in range(-qu, qu+1):
                j = (2 * qm + 1) * (u + qm) + (v + qm)

                wave_x = wave_function(x, u, dim[0])
                wave_y = wave_function(y, v, dim[1])
                wave_dx = d_wave_function(x, u, dim[0])
                wave_dy = d_wave_function(y, v, dim[1])

                dx_dxi += wave_dx * wave_y * coeff[j]
                dy_dxi += wave_x * wave_dy * coeff[j]

    return dx_dxi, dy_dxi


def ddxy_ddxi(x, y, coeff, qm, qu, dim):
    """
    ddxy_ddxi(x, y, coeff, qm, qu, dim)

    Function returning second derivatives of intrinsic surface
    at position (x,y) wrt x and y

    Parameters
    ----------

    x:  float
        Coordinate in x dimension
    y:  float
        Coordinate in y dimension
    coeff:	float, array_like; shape=(n_waves**2)
        Optimised surface coefficients
    qm:  int
        Maximum number of wave frequencies in Fourier Sum
        representing intrinsic surface
    qu:  int
        Upper limit of wave frequencies in Fourier Sum
        representing intrinsic surface
    dim:  float, array_like; shape=(3)
        XYZ dimensions of simulation cell

    Returns
    -------

    ddx_ddxi:  float
        Second derivative of intrinsic surface in x dimension
    ddy_ddxi:  float
        Second derivative of intrinsic surface in y dimension

    """

    if np.isscalar(x):
        u_array, v_array = wave_arrays(qm)
        indices = wave_indices(qu, u_array, v_array)

        wave_x = wave_function_array(x, u_array[indices], dim[0])
        wave_y = wave_function_array(y, v_array[indices], dim[1])
        wave_ddx = dd_wave_function_array(x, u_array[indices], dim[0])
        wave_ddy = dd_wave_function_array(y, v_array[indices], dim[1])

        ddx_ddxi = np.sum(wave_ddx * wave_y * coeff[indices])
        ddy_ddxi = np.sum(wave_x * wave_ddy * coeff[indices])

    else:
        ddx_ddxi = np.zeros(x.shape)
        ddy_ddxi = np.zeros(x.shape)
        for u in range(-qu, qu+1):
            for v in range(-qu, qu+1):
                j = (2 * qm + 1) * (u + qm) + (v + qm)

                wave_x = wave_function(x, u, dim[0])
                wave_y = wave_function(y, v, dim[1])
                wave_ddx = dd_wave_function(x, u, dim[0])
                wave_ddy = dd_wave_function(y, v, dim[1])

                ddx_ddxi += wave_ddx * wave_y * coeff[j]
                ddy_ddxi += wave_x * wave_ddy * coeff[j]

    return ddx_ddxi, ddy_ddxi


def xi_var(coeff, qm, qu):
    """Calculate average variance of surface heights

    Parameters
    ----------
    coeff:	float, array_like; shape=(n_frame, n_waves**2)
        Optimised surface coefficients
    qm:  int
        Maximum number of wave frequencies in Fourier Sum
        representing intrinsic surface
    qu:  int
        Upper limit of wave frequencies in Fourier Sum
        representing intrinsic surface

    Returns
    -------
    calc_var: float
        Variance of surface heights across whole surface

    """

    u_array, v_array = wave_arrays(qm)
    indices = wave_indices(qu, u_array, v_array)

    Psi = vcheck(u_array[indices], v_array[indices]) / 4.

    coeff_filter = coeff[:, :, indices]
    mid_point = len(indices) / 2

    av_coeff = np.mean(coeff_filter[:, :, mid_point], axis=0)
    av_coeff_2 = np.mean(coeff_filter**2, axis=(0, 1)) * Psi

    calc_var = np.sum(av_coeff_2) - np.mean(av_coeff**2, axis=0)

    return calc_var
