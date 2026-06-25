from .model import BKTState


def update_bkt_posterior(state: BKTState, is_correct: bool) -> BKTState:
    """Standard BKT Bayesian update after one observation."""
    p = state.params
    current = state.p_know

    if is_correct:
        p_obs_given_know = 1.0 - p.p_s
        p_obs_given_not_know = p.p_g
    else:
        p_obs_given_know = p.p_s
        p_obs_given_not_know = 1.0 - p.p_g

    likelihood = p_obs_given_know * current
    marginal = likelihood + p_obs_given_not_know * (1.0 - current)

    if marginal == 0:
        p_know_given_obs = current
    else:
        p_know_given_obs = likelihood / marginal

    new_p_know = p_know_given_obs + (1.0 - p_know_given_obs) * p.p_t

    return BKTState(params=p, p_know=min(new_p_know, 0.999))
