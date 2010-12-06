# -*- coding: utf-8 -*- So we can write unicode chars in code.
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
# Description:
#  Minimalistic latex writer for docutils.
#  Should be resilient, so output warnings if cannot produce certain pieces of
#  output.
#
# Author       : Nick Blundell
# Organisation : www.nickblundell.org.uk
#

# Ref: http://docutils.sourceforge.net/docs/
# Ref: /usr/lib/python2.6/site-packages/docutils/writers/newlatex2e/__init__.py
# Ref: tools/old/nicklatex.py

import inspect
from docutils import writers, nodes, utils
from docutils.parsers.rst import directives, Directive, roles

from nbdebug import d

VERSION = "1.0"

#################################################################
# Writer
#

class Writer(writers.Writer):
  """Main class used by doctutils to write the parsed document."""

  def __init__(self, template="template.tex", extension_module=None, source_filename=None):
    writers.Writer.__init__(self)
    
    self.translator_class = None
    self.source_filename = source_filename
    

    # See if a custom LatexTranslator has been passed in a module.
    self.extension_module = None
    if extension_module :
      self.extension_module = self._import_module(extension_module)
      for item_name, item in self.extension_module.__dict__.iteritems() :
        if inspect.isclass(item) and issubclass(item, LatexTranslator) :
          self.translator_class = item
          break;
    
    if not self.translator_class :
      self.translator_class = LatexTranslator

    self.register_document_elements()

    self.template = template

  def register_document_elements(self) :
    # Register roles
    for item_name in dir(self.translator_class) :
      # Normal roles
      if item_name.startswith("role_") :
        role_name = item_name.replace("role_", "")
        roles.register_canonical_role(role_name, generic_inline_role)
        d("Registered (normal) role %s" % role_name)
      # Raw roles.
      elif item_name.startswith("raw_role_") :
        role_name = item_name.replace("raw_role_", "")
        roles.register_canonical_role(role_name, generic_raw_role)
        d("Registered raw role %s" % role_name)

    # Register directives, first from this module, the from an extension module, so can overload.
    items = globals()
    if self.extension_module :
      items.update(self.extension_module.__dict__)
    for item_name, item in items.iteritems() :
      if inspect.isclass(item) and issubclass(item, WriterDirective) and item != WriterDirective:
        d("Registering directive %s" % item_name)
        directives.register_directive(item.__name__, item)


  def translate(self):
    # Create our translator, which will generate parts of the document.
    visitor = self.translator_class(self.document, writer=self)
    
    # This sets off the writing of document nodes.
    self.document.walkabout(visitor)
    
    #
    # Set the render parts, which are simply attributes of the writer and 'output' is
    # a special rendering of the whole document
    #
    
    self.output = visitor.astext()
    
  def _import_module(self, module_file) :
    """Import a module by its path."""
    if not module_file :
      return None
    import os, sys
    mod_dir = os.path.dirname(module_file)
    module_name = os.path.basename(module_file).rstrip(".py")
    if mod_dir :
      sys.path.append(mod_dir)
    return __import__(module_name)

#################################################################
# Translator
#

# We use this string to split latex commands over node content,
# which is very useful and saves lots of duplication.
NODE_CONTENT = "__NODE_CONTENT__"

class LatexTranslator(nodes.NodeVisitor):
  """As document nodes are visited, turns them into output for one or more document parts."""

  def __init__(self, document, writer):
    self.writer = writer
    nodes.NodeVisitor.__init__(self, document)
    self.body = []
    self.title = []
    self.abstract = []
    self.verbatim = False
    self.section_level = 0
    self.context_stack = []
    self.double_quote_state = 0 # For automatically opening and closing double quotes.

    # For handling switch between content parts
    self.part_stack = []
    self.current_part = self.body


    # Initialise text mappings used for encoding text as latex.
    self.text_mappings = self.initialise_text_mappings()
    # Sorted so longest first, to allow for phrases to be replaced before
    # individual chars.
    self.sorted_mapping_targets = sorted(self.text_mappings.keys(), key=lambda target: len(target), reverse=True)

    self.parts = ["body", "title", "abstract"]



  def astext(self):
    """Joins all parts into main doc string."""
    output = open(self.writer.template, "r").read()
    for part in self.parts :
      try :
        output = output.replace("[%s]" % part.upper(), ''.join(getattr(self, part)))
      except AttributeError :
        pass

    return output

  def append(self, s, part="body") :
    """Adds a string to a part of the output."""
    self.current_part.append(s)

  def set_current_part(self, part) :
    if self.current_part is part :
      return

    self.part_stack.append(self.current_part)
    self.current_part = part

  def unset_current_part(self) :
    if len(self.part_stack) > 0 :
      self.current_part = self.part_stack.pop()
    else :
      self.current_part = self.body

  #
  # Text encoding
  #

  def initialise_text_mappings(self) :

    text_mappings = {
      "--": "--",   # En-dash
      u"\u2014": "--",   # En-dash
      u"\u2013": "-",   # dash
      "---": "---", # Em-dash
      "...": r"{\ldots}",
      "->": r"$\rightarrow$",
      "<-": r"$\leftarrow$",
      u"\u00ef": r"""\"i""",
    }

    latin_phrases = {
      'e.g. ' : r"e.g.~",
      'i.e. ' : r"i.e.~",
      'e.g.\n' : r"e.g.~",
      'i.e.\n' : r"i.e.~",
      'etc.' : r"etc.",
      'et al.' : r"et al.",
      'et al. ' : r"et al.~",
      'c.f. ' : r"c.f~",
      'c.f.\n' : r"c.f~",
    }
    for target in latin_phrases :
      text_mappings[target] = r"\emph{%s}" % latin_phrases[target]

    

    # Perhaps can automate the newline thing.

    character_map = {
      u'\\': r'{\textbackslash}',
      '{': r'{\{}',
      '}': r'{\}}',
      '$': r'{\$}',
      '&': r'{\&}',
      '%': r'{\%}',
      '#': r'{\#}',
      '[': r'{[}',
      ']': r'{]}',
      '-': r'{-}',
      '`': r'{`}',
      "'": r"{'}",
      ',': r'{,}',
      '"': r'{"}', # XXX
      '|': r'{\textbar}',
      '<': r'{\textless}',
      '>': r'{\textgreater}',
      '^': r'{\textasciicircum}',
      '~': r'$\sim$',
      '_': r'{\_}',
      u'£': u'{\\pounds}',
      u'\u201c': "``",
      u'\u201d': "\"",
      u"\u2019": "'",
      u"\u2026": r"\ldots",
      u"...": r"\ldots",
    }
    text_mappings.update(character_map)

    from docutils.writers.newlatex2e import unicode_map
    unicode_map = unicode_map.unicode_map # comprehensive Unicode map
    character_map.update(unicode_map)
    
    return text_mappings


  def encode(self, text, verbatim=False) :
    """Encodes a piece of unicode text as latex, replacing chars and phrases with the text_mappings."""
    if self.verbatim :
      verbatim = True

    if verbatim :
      return text

    # Allow for phrase substitution.
    latex_text = []
    while text :
      latex_term = None
      
      # Handle quotation marks
      # TODO: Botches up inside texttt text since dows not handle `` - get a square in pdf
      #if text[0] == "\"" :
      #  latex_term = self.double_quote_state and "\"" or "``"
      #  self.double_quote_state = (self.double_quote_state + 1) % 2
      #  text = text[1:]
      
      # Look for a substitution
      if not latex_term :
        for target in self.sorted_mapping_targets :
          if text.startswith(target) :
            latex_term = self.text_mappings[target]
            text = text[len(target):] # Reduce text
            break
      if not latex_term :
        latex_term = text[0]
        text = text[1:] # Reduce text
      latex_text.append(latex_term)
    
    return ''.join(latex_text)

  #
  # Latex shortcuts
  #

  def begin_end(self, environment, content=NODE_CONTENT, args=None) :
    if args :
      args = "[%s]" % args
    else :
      args = ""
    output = """\\begin{%s}\n%s%s\n\\end{%s}""" % (environment, args, content, environment)
    return "\n\n%s\n\n" % output  # Lack of newlines seems to affect latex in some cases.

  def latex_command(self, command, content=NODE_CONTENT, args=None):
    if args :
      args = "[%s]" % args
    else :
      args = ""
    
    # Some latex commands have no content, and therefore no brackets.
    if content == None :
      content_part = ""
    else :
      content_part = "{%s}" % content

    return r"""\%s%s%s""" % (command, args, content_part)

  def surround_content(self, prefix, suffix, content=NODE_CONTENT) :
    return prefix + content + suffix

  def dict_to_latex_options(self, options) :
    return ",".join(["%s=%s" % (option,value) for option, value in options.iteritems()])

  def set_colour(self, colour, content) :
    return self.surround_content("{" + self.latex_command("color", colour) , "}", content)

  #
  # Useful functions for splitting text over a node's content.
  #

  def split_and_push(self, text): 
    """Splits output over node content, so second part can be popped off stack on depart."""
    parts = text.split(NODE_CONTENT)
    try :
      self.context_stack.append(parts[1])
    except :
      self.context_stack.append("")
    self.append(parts[0])

  def pop_context(self) :
    """Pops from the stack to the body."""
    self.append(self.context_stack.pop())


  #
  # Built-in node translators
  #

  def visit_title(self, node) :
    """Use this only for the main document title, since our sections write the title."""
    if self.section_level == 0 :
      self.title = self.encode(node.astext())
    raise nodes.SkipNode

  def visit_Text(self, node):
    """Simple text node."""
    self.append(self.encode(node.astext()))
 

  def visit_raw(self, node):
    """Adds raw text directly to output."""
    if hasattr(node, "role_name") :
      role_function = getattr(self, "raw_role_%s" % node.role_name)
      self.append(role_function(node))
    
    raise nodes.SkipNode # So we don't descend further into the node.

  def visit_literal(self, node):
    self.append((node.astext()))
    raise nodes.SkipNode # So we don't descend further into the node.

  #
  # Section node handling
  #
  

  def visit_section(self, node):
    
    # Get the title node, assuming the first node of a section is its title.
    title_node = node.children[0]
    title_text = title_node.astext()
    assert isinstance(title_node, nodes.title)

    # Increase the section level.
    self.section_level += 1
    
    # Add the section to give us more flexibility in processing sections.
    self.visit_titled_section(title_text, node)
  
  def depart_section(self, node):

    # Get the title node, assuming the first node of a section is its title.
    title_node = node.children[0]
    title_text = title_node.astext()
    assert isinstance(title_node, nodes.title)
    
    # Add the section to give us more flexibility in processing sections.
    self.depart_titled_section(title_text, node)
    
    # Decrese the section level.
    self.section_level -= 1

  def visit_titled_section(self, title_text, node) :
    # Handle special sections.
    hook_output = self.write_titled_section(title_text, node)
    if hook_output :
      self.split_and_push(hook_output)
      return

    # Handle main title
    #if self.section_level == 0:
    #  self.title = self.encode(title_text)
    #  self.context_stack.append("") # Push empty, since we always pop on depart.
    #  return
      

    # Handle abstract.
    if title_text.lower().strip() == "abstract":
      self.set_current_part(self.abstract)
      return
    
    # Handle default section
    latex_section = ["section", "subsection", "subsubsection"][self.section_level-1]
    output = self.latex_command(latex_section, self.encode(title_text))
    output = "\n\n%s\n\n" % output
    self.split_and_push(output)

  def depart_titled_section(self, title_text, node) :
    # Handle abstract.
    if title_text.lower().strip() == "abstract":
      self.unset_current_part()
    self.pop_context()

  
  def write_titled_section(self, title_text, node):
    """Allows subclass to hook into section behaviour (e.g. for beamer frames, etc.)."""
    return None


  #
  # Write functions, which embody visit and depart by simply splitting over
  # content
  #

  def write_paragraph(self, node) :
    return self.surround_content("\n","\n")
  
  def write_emphasis(self, node) :
    return self.latex_command("emph")

  def write_strong(self, node) :
    return self.latex_command("textbf")
    
  def write_cite(self, node) :
    return self.latex_command("cite")

  def write_bullet_list(self, node) :
    return self.begin_end("itemize")
 

  def write_enumerated_list(self, node) :
    return self.begin_end("enumerate")

  def write_list_item(self, node) :
    return self.latex_command("item")

  # XXX: Need to skip node and use raw text.
  #def write_reference(self, node) :
  #  if node.astext().lower().startswith("http") :
  #    # Need \usepackage{hyperref}
  #    return self.latex_command("url", )

  def write_definition_list(self, node) :
    return self.begin_end("description")
 
  def write_definition(self, node) :
    return ""
    return self.latex_command("item", content=None, args=NODE_CONTENT)

  def write_term(self, node) :
    return self.latex_command("item", content=None, args=NODE_CONTENT)
  
  def write_definition_list_item(self, node) :
    return self.surround_content("{","}")


  #
  # Roles
  #


  def visit_inline(self, node) :
    if hasattr(node, "role_name") :
      role_function = getattr(self, "role_%s" % node.role_name)
      self.split_and_push(role_function(node))

  def depart_inline(self, node) :
    if hasattr(node, "role_name") :
      self.pop_context()

    
  def role_footnote(self, node) :
    return self.latex_command("footnote")

  def role_quote(self, node) :
    return "`" + NODE_CONTENT + "'"
  
  def role_dquote(self, node) :
    return "``" + NODE_CONTENT + "\""

  def role_code(self, node) :
    return self.set_colour("blue", self.latex_command("texttt"))

  def raw_role_math(self, node) :
    return "$%s$" % node.astext()
 
  def raw_role_url(self, node) :
    return self.latex_command("url", node.astext())
  raw_role_hyperlink = raw_role_url # url doesn't seem to work

  def raw_role_cite(self, node) :
    return self.latex_command("cite", node.astext())
  
  def raw_role_label(self, node) :
    return self.latex_command("label", node.astext())
  
  def raw_role_latex(self, node) :
    """Raw latex role."""
    return node.astext()
  
  def raw_role_ref(self, node) :
    return self.latex_command("ref", node.astext())
  


  #
  # Ignored nodes
  #
  def visit_ignore(self, node) : pass
  def visit_ignore_and_skip(self, node) : raise nodes.SkipNode # So we don't descend further into the node.
  
  visit_document = visit_ignore
  visit_subtitle = visit_ignore
  visit_reference = visit_ignore
  visit_comment = visit_ignore_and_skip
  #visit_enumerated = visit_ignore
  #visit_enumerated_list = visit_ignore


  #
  # Catch-alls and auto routing to writer functions.
  #

  def unimplemented_visit(self, node):
    self.append(r"{\color{red}" + self.encode("[UNIMPLEMENTED %s]" % class_name) + "}")

  def unimplemented_depart(self, node):
    pass

  # Allows us to attach rendering code to nodes.
  def unknown_visit(self, node):
    
    # Automate split_and_push for write_*** functions
    class_name = node.__class__.__name__
    write_function = "write_%s" % class_name
    if hasattr(self, write_function) :
      self.split_and_push(getattr(self, write_function)(node))
      return

    # Our directive nodes encapsulate their writer functions.
    if hasattr(node, "directive") :
      node.directive.visit(self, node)
      return
    
    self._warning("[UNKNOWN %s]" % node.__class__.__name__)

  def unknown_departure(self, node):
    
    # Automate split_and_push
    class_name = node.__class__.__name__
    write_function = "write_%s" % class_name
    if hasattr(self, write_function) :
      self.pop_context()
      return
    
    # Check if this node is a writer too
    if hasattr(node, "directive") :
      node.directive.depart(self, node)
      return

  #
  # Helpers
  #

  def _warning(self, text) :
    """Add a red warning message to the output."""
    self.append(self.surround_content(
      "{" + self.latex_command("color", "red"),
      "}",
      self.encode(text),
    ))



###############################
# Generic role generators.
#

def generic_inline_role(role, rawtext, text, lineno, inliner, options={}, content=[]):
  node = nodes.inline(rawtext, utils.unescape(text), **options)
  node.role_name = role
  return [node], []

def generic_raw_role(role, rawtext, text, lineno, inliner, options={}, content=[]):
  options["format"] = "latex"
  # docutils sets literal backslash to \x00 in text, so undo this for literal output.
  text = text.replace("\x00","\\")
  node = nodes.raw(rawtext, text, **options)
  node.role_name = role
  return [node], []


#################################################################
# Directive classes
#

# We use this unknown node type, so our writer handles it with unknown.
# We are bastardising docutils so we can conveniently join together
# directives and their writer code.

# A node for general use.
class GenericNode(nodes.comment): pass

class WriterDirective(Directive) :
  
  # Some defaults
  optional_arguments = 10 # Keeps things flexible for optional unnamed args.
  final_argument_whitespace = False
  option_spec = { }
  has_content = True
  
  # See here: http://docutils.sourceforge.net/docs/howto/rst-directives.html
  def _create_node(self, parse_content=True) :
    """Creates a node to represent parsed directive."""
    node = GenericNode()
    
    # If the directive has content, we will want to run it through the parser.
    if parse_content and self.content :
      nnode = nodes.Element()          # anonymous container for parsing
      self.state.nested_parse(self.content, self.content_offset, nnode)
      first_node = nnode[0]
      if isinstance(first_node, nodes.paragraph):
        node += first_node
        
    # Automatically store any labelled options on the node
    for key in self.option_spec.keys() :
      setattr(node, key, self.options.get(key, None))
    setattr(node, "args", self.arguments)

    # Give a pointer to this class to the node, so we can call visit/depart
    node.directive = self.__class__
    
    return node
 
  # Note, can define a write method if content is automatically to be split over a node
  """
  @staticmethod
  def write(writer, node):
    ...
    return output
  """

  @classmethod
  def visit(cls, writer, node):
    if hasattr(cls, "write") :
      writer.split_and_push(cls.write(writer, node))
      return
    raise NotImplementedError

  @classmethod
  def depart(cls, writer, node):
    if hasattr(cls, "write") :
      writer.pop_context()
      return
    raise NotImplementedError

#################################################################
# Directives
#

class image(WriterDirective):

  required_arguments = 1 # Filename
  option_spec = {
    'scale': directives.unchanged,
    'positioning': directives.unchanged,
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
      figure_env = "figure*"
    else :
      figure_env = "figure"

    if node.positioning :
      env_args = node.positioning
    else:
      env_args = None #"htb" # Figure positioning

    if "no_caption" in node.args :
      caption_command = ""
    else :
      caption_command = latex_command("caption")

    output = begin_end(figure_env,
      latex_command("centering", None) + graphic_command + caption_command + latex_command("label",node.label),
      args=env_args,
    )

    if "no_caption" in node.args :
      writer.append(output)
      raise nodes.SkipNode

    return output
 

class literal_include(WriterDirective):
  """Requires listings latex package."""

  required_arguments = 1 # filename
  option_spec = {
    'language': directives.unchanged,
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
    
    begin_end, latex_command = writer.begin_end, writer.latex_command

    # Allow for simple verbatim inclusion
    if "verbatim" in node.args :
      return latex_command("verbatiminput", node.filename)

    output = ""
    # Note listing seems only to preserve indentation whitespace
    options = {
      #"stringstyle":r"\ttfamily",
      "stringstyle":r"\texttt",  # Think this is for quoted strings
      "showstringspaces":r"false",
      "basicstyle":r"\scriptsize\ttfamily", # This is for main text style
      #"basicstyle":r"\small", # This is for main text style
      "keywordstyle":r"\color{blue}",
      "frame":"single",
      "columns":"fullflexible",  # Helps with listings in columns.
    }
    if node.language :
      options["language"] = node.language
    
    
    output += latex_command("lstset", writer.dict_to_latex_options(options))

    listing_command = latex_command("lstinputlisting", node.filename)
  
    if "span_columns" in node.args :
      figure_env = "figure*"
    else :
      figure_env = "figure"

    if "no_caption" in node.args :
      caption_command = ""
    else :
      caption_command = latex_command("caption")


    output += begin_end(figure_env,
      latex_command("centering", None) + listing_command + caption_command + latex_command("label",node.label),
      args="htb"
    )
  

    if "no_caption" in node.args :
      writer.append(output)
      raise nodes.SkipNode

    return output


