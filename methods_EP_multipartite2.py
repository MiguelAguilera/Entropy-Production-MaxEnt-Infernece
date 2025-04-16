import torch

import numpy as np

# =======================
# Spin Model and Correlations
# =======================

def exp_EP_spin_model(Da, J, i):
    """
    Compute empirical entropy production contribution from spin `i` using 
    correlation matrix Da and interaction matrix J.
    """
    #return torch.sum((J[i, :] - J[:, i]) * Da) / 2
    return J[i, :] @ Da

def correlations(S, i):
    """
    Compute pairwise correlations for spin `i`, averaged over Tetitions.
    """
    Da = torch.einsum('r,jr->j', (-2 * S[i, :]), S) / S.shape[1]
    return Da

def correlations4(S, i):
    """
    Compute 4th-order correlation matrix for spin `i`.
    """
    K = (4 * S) @ S.T / S.shape[1]
    return K

# =======================
# Correlations with Theta (weighted by model parameters)
# =======================

def correlations_theta(S, theta, i):
    """
    Compute weighted pairwise correlations using theta.
    THESE ARE NOT YET DIVIDED BY THE NORMALIZATION CONSTANT.
    """
    S_without_i = torch.cat((S[:i, :], S[i+1:, :]))  # remove spin i
    thf = (-2 * S[i, :]) * torch.matmul(theta, S_without_i)
    S1_S = -(-2 * S[i, :]) * torch.exp(-thf)
    Da = torch.einsum('r,jr->j', S1_S, S) / S.shape[1]
#    Da[i] = 0
    return Da

def correlations4_theta(S, theta, i):
    """
    Compute weighted 4th-order correlations using theta.
    THESE ARE NOT YET DIVIDED BY THE NORMALIZATION CONSTANT.
    """
    S_without_i = torch.cat((S[:i, :], S[i+1:, :]))
    thf = (-2 * S[i, :]) * torch.matmul(theta, S_without_i)
    K = (4 * torch.exp(-thf) * S) @ S.T / S.shape[1]
#    K[i, :] = 0
#    K[:, i] = 0
    return K

# =======================
# Partition Function Estimate
# =======================

def log_norm_theta(S, theta, i):
    """
    Estimate normalization constant Z from the partition function under theta.
    """
    S_without_i = torch.cat((S[:i, :], S[i+1:, :]))
    thf = (-2 * S[i, :]) * torch.matmul(theta, S_without_i)

    return  torch.logsumexp(-thf, dim=0) - torch.log(torch.tensor(thf.numel()))

    # Z = torch.mean(torch.exp(-thf))
    # return Z

# =======================
# Matrix Processing Utilities
# =======================

def K_nodiag(Ks, i):
    """
    Remove the i-th row and column from matrix Ks.
    """
    Ks_no_row = torch.cat([Ks[:i, :], Ks[i+1:, :]], dim=0)
    Ks_no_row_col = torch.cat([Ks_no_row[:, :i], Ks_no_row[:, i+1:]], dim=1)
    return Ks_no_row_col

def remove_i(A, i):
    """
    Remove the i-th element from a 1D tensor A.
    """
    r = torch.cat((A[:i], A[i+1:]))
    return r

# =======================
# Linear Solver for Theta Estimation
# =======================

def solve_linear_theta(Da, Da_th, Ks_th, i):
    """
    Solve the linear system to compute theta using regularized inversion.
    """
    Dai    = remove_i(Da, i)
    Dai_th = remove_i(Da_th, i)
    Ks_no_diag_th = K_nodiag(Ks_th, i)

    rhs_th = Dai - Dai_th

    I = torch.eye(Ks_no_diag_th.size(-1), dtype=Ks_th.dtype)
    
    alpha = 1e-4*torch.trace(Ks_no_diag_th)/len(Ks_no_diag_th)
    dtheta = torch.linalg.lstsq(Ks_no_diag_th + alpha*I, rhs_th).solution

    # epsilon = 1e-6
    # I = torch.eye(Ks_no_diag_th.size(-1), dtype=Ks_th.dtype)

    # while True:
    #     try:
    #         dtheta = torch.linalg.solve(Ks_no_diag_th + epsilon * I, rhs_th)
    #         break
    #     except torch._C._LinAlgError:
    #         epsilon *= 10  # Increase regularization if matrix is singular
    #         print(f"Matrix is singular, increasing epsilon to {epsilon}")

    return dtheta

# =======================
# Entropy Production Estimators
# =======================

def get_EP_Newton(S, i):
    """
    Compute entropy production estimate using the 1-step Newton method and the MTUR method for spin i.
    """
    Da = correlations(S, i)
    Ks = correlations4(S, i)
    Ks -= torch.einsum('j,k->jk', Da, Da)


    
    theta = solve_linear_theta(Da, -Da, Ks, i)
    Dai = remove_i(Da, i)
    
    lnZ = log_norm_theta(S, theta, i)

    sig_MTUR = theta @ Dai

    Dai = remove_i(Da, i)
    sig_N1 = (theta * Dai).sum() - lnZ

    return sig_N1, sig_MTUR, theta, Da

def get_EP_Newton2(S, theta_lin, Da, i):
    """
    One iteration of Newton-Raphson to refine theta estimation.
    """
    N, _ = S.shape
    Da_th = correlations_theta(S, theta_lin, i)
    Ks_th = correlations4_theta(S, theta_lin, i)


    Z = np.exp(log_norm_theta(S, theta_lin, i))
    Da_th /= Z
    Ks_th = Ks_th / Z - torch.einsum('j,k->jk', Da_th, Da_th)

    theta_lin2 = solve_linear_theta(Da, Da_th, Ks_th, i)
    theta = theta_lin + theta_lin2

    Dai = remove_i(Da, i)
    t_min = theta.min()
    sig_N2 = (theta * Dai).sum() - log_norm_theta(S, theta, i)
    
    return sig_N2, theta_lin2

