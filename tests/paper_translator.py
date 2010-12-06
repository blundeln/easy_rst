#
# Copyright (C) 2010 Nick Blundell.
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
# 
# The GNU GPL is contained in /usr/doc/copyright/GPL on a Debian
# system and in the file COPYING in the Linux kernel source.
# 
# paper_translator (paper_translator.py)
# --------------------------------------
#
# Description:
#  Example translator extension.
#
# Author       : Nick Blundell
# Organisation : www.nickblundell.org.uk
# Version Info : $Id$
#

import rst_tex
from rst_tex import LatexTranslator, WriterDirective

class MyTranslator(LatexTranslator) :

  def role_code(self, node) :
    return self.set_colour("blue", self.latex_command("texttt"))


class image(WriterDirective):
  """This should overload the image directive in module rst_tex."""
  required_arguments = 1 # Filename
  option_spec = {
    'scale': rst_tex.directives.unchanged,
  }

  def run(self):
    node = self._create_node()
    node.filename = node.args[0]
    import os
    # Use filename as label.
    node.label = os.path.basename(node.filename).split(".")[0]
    return [node]
 
  @staticmethod
  def write(writer, node):
    if node.scale :
      options = "scale=%s" % node.scale
    else :
      options = None
    
    begin_end, latex_command = writer.begin_end, writer.latex_command
    
    graphic_command = latex_command("includegraphics", node.filename, options)

    if "span_columns" in node.args :
      figure_env = "fixxxxgure*"
    else :
      figure_env = "fixxxgure"

    env_args = None #"htb" # Figure positioning

    output = begin_end(figure_env,
      latex_command("centering", None) + graphic_command + latex_command("caption") + latex_command("label",node.label),
      args=env_args,
    )
    
    return output
 
