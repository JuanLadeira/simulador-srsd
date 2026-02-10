"""
SRSD Simulator - Sistema de Roteamento Seguro Distribuído

A network simulator for validating the SRSD routing algorithm,
demonstrating that:
- H1: Structural routing predictability is an exploitable vulnerability
- H2: SRSD with QKD reduces vulnerability without significant performance loss
"""

__version__ = "0.1.0"
__author__ = "SRSD Research Team"

from . import core
from . import routing
from . import adversary
from . import qkd
from . import simulation
from . import analysis

__all__ = [
    'core',
    'routing',
    'adversary',
    'qkd',
    'simulation',
    'analysis',
]
