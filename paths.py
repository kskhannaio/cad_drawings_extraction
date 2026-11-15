"""Where the pipeline reads and writes. Every step imports from here.

Override the folders with environment variables:
  PIPELINE_DOCS   folder holding the source PDFs   (default: ../../docs)
  PIPELINE_OUT    folder for everything produced   (default: ./out)
"""
import os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DOCS = os.environ.get('PIPELINE_DOCS', os.path.abspath(os.path.join(ROOT, '..', '..', 'docs')))
OUT = os.environ.get('PIPELINE_OUT', os.path.join(ROOT, 'out'))
OSM = os.path.join(ROOT, 'osm')
os.makedirs(OUT, exist_ok=True)

# source documents
TENDER_PDF = os.path.join(DOCS, 'Ejipura to Silk Board Schedule A B C D F H I.pdf')    # B-SMILE tender, drawings on pages 24-40
OD_PDF = os.path.join(DOCS, 'OD and Toll Analysis OMR to Silk Board.pdf')              # traffic and toll tables, 6 pages

# SUMO ships as a pip package (eclipse-sumo); sumolib reads road networks, netconvert builds them from OpenStreetMap
import sumo  # noqa: E402
os.environ['SUMO_HOME'] = sumo.SUMO_HOME
sys.path.insert(0, os.path.join(sumo.SUMO_HOME, 'tools'))
import sumolib  # noqa: E402
NETCONVERT = os.path.join(sumo.SUMO_HOME, 'bin', 'netconvert')
