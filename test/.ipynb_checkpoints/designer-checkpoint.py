import os, sys
import wx
import wx.lib
import wx.lib.ogl as ogl
try:
    from wx.lib.wordwrap import wordwrap
except ImportError:
    wordwrap = lambda text, width, dc: text

try:
    from template import Template
except ImportError:
    # we are frozen?
    from fpdf.template import Template
