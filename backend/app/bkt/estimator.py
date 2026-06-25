import math
from .model import BKTParams


class BKTEstimator:
    """
    Fit personalized BKT parameters from a sequence of observed answers using EM.
    Each observation = (is_correct, previous_p_know).

    The HMM has two latent states: K (knows), N (not-knows).
    Learning transition happens AFTER the observation.
    """

    def fit(self, observations: list[bool], init_params: BKTParams = None,
            max_iter: int = 50, tol: float = 1e-4) -> BKTParams:
        if len(observations) < 5:
            return init_params or BKTParams()

        # Initialize parameters
        p_l0, p_t, p_g, p_s = 0.50, 0.20, 0.15, 0.10
        if init_params:
            p_l0, p_t, p_g, p_s = init_params.p_l0, init_params.p_t, init_params.p_g, init_params.p_s

        for _ in range(max_iter):
            # E-step: forward-backward + posterior
            alphas, betas = self._forward_backward(observations, p_l0, p_t, p_g, p_s)
            gamma = [a * b for a, b in zip(alphas, betas)]
            total = sum(gamma)
            gamma = [g / total if total > 0 else 0.5 for g in gamma]

            # M-step
            new_p_g = sum((1 - g) * (1 if o else 0) for g, o in zip(gamma, observations))
            new_p_g /= max(sum(1 - g for g in gamma), 1e-6)
            new_p_s = sum(g * (0 if o else 1) for g, o in zip(gamma, observations))
            new_p_s /= max(sum(g for g in gamma), 1e-6)

            new_p_t_denom = sum(1 - g for g in gamma[:-1])
            new_p_t_num = sum((gamma[i + 1] - gamma[i]) for i in range(len(gamma) - 1) if gamma[i + 1] > gamma[i])
            new_p_t = max(0.01, min(0.50, new_p_t_num / max(new_p_t_denom, 1e-6)))

            # Check convergence
            if all(abs(a - b) < tol for a, b in [(new_p_g, p_g), (new_p_s, p_s), (new_p_t, p_t)]):
                break

            p_g, p_s, p_t = new_p_g, new_p_s, new_p_t

        return BKTParams(
            p_l0=max(0.01, min(0.99, p_l0)),
            p_t=max(0.01, min(0.50, p_t)),
            p_g=max(0.01, min(0.40, p_g)),
            p_s=max(0.01, min(0.40, p_s)),
        )

    def _forward_backward(self, obs: list[bool], p_l0, p_t, p_g, p_s):
        T = len(obs)
        alpha = [0.0] * T
        beta = [0.0] * T

        # Forward
        obs0 = 1.0 - p_s if obs[0] else p_s
        obs0_n = p_g if obs[0] else 1.0 - p_g
        alpha[0] = p_l0 * obs0 + (1 - p_l0) * obs0_n

        for t in range(1, T):
            p_know_prev = p_l0 if t == 1 else alpha[t - 1]
            trans_know = p_know_prev * (1.0 - p_s if obs[t] else p_s)
            trans_not_know = (1 - p_know_prev) * (p_g if obs[t] else 1.0 - p_g)
            alpha[t] = trans_know + trans_not_know

        # Backward
        beta[T - 1] = 1.0
        for t in range(T - 2, -1, -1):
            p_know = p_l0
            trans_know = p_know * (1.0 - p_s if obs[t + 1] else p_s) * beta[t + 1]
            trans_not_know = (1 - p_know) * (p_g if obs[t + 1] else 1.0 - p_g) * beta[t + 1]
            beta[t] = trans_know + trans_not_know

        return alpha, beta
