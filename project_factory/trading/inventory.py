"""Inventory tracking + the reservation-price inventory penalty
(section 6 Archetype B: r_t = m_t + alpha*mu_hat_t - gamma*q_t)."""

from __future__ import annotations

import numpy as np


def clip_inventory(inventory: float, max_inventory: float) -> float:
    return float(np.clip(inventory, -max_inventory, max_inventory))


def inventory_skew(inventory: float, gamma: float) -> float:
    """The -gamma*q_t term: positive inventory (long) pushes the
    reservation price down (encourages selling); negative inventory
    (short) pushes it up (encourages buying)."""
    return -gamma * inventory
