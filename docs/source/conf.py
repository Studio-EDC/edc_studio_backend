# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# Añadir el directorio raíz del proyecto al path
import os
import sys

# Ruta absoluta del proyecto raíz
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
APP_PATH = os.path.join(PROJECT_ROOT, 'app')

sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, APP_PATH)

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'EDC Studio Backend'
copyright = '2025, Itziar Mensa Minguito'
author = 'Itziar Mensa Minguito'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',           # Documentación automática desde docstrings
    'sphinx.ext.napoleon',          # Soporte para docstrings estilo Google/NumPy
    'sphinx_autodoc_typehints',     # Muestra los type hints de Python
    'myst_parser'                   # Permite incluir Markdown (.md)
]

# Incluye el README.md principal en la documentación
source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

templates_path = ['_templates']
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

# Opcional: mejora el estilo de las tablas y ancho del contenido
html_theme_options = {
    'collapse_navigation': False,
    'navigation_depth': 4,
    'titles_only': False
}

# -- Autodoc configuration ---------------------------------------------------

# Incluye el docstring de la clase y del __init__
autoclass_content = 'both'
# Ordena miembros como aparecen en el código
autodoc_member_order = 'bysource'
# Excluye métodos privados (_method)
autodoc_default_options = {
    'members': True,
    'undoc-members': False,
    'private-members': False,
    'show-inheritance': True,
}

