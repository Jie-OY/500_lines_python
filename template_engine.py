import re


class CodeBuilder(object):
    """Build source code  conveniently  """

    def __init__(self, indent=0):
        self.code = []
        self.indent_level = indent

    def add_line(self, line):
        """
        Add a line of source to the code
        Indentation and newline will add for you, don't provide them.
        :param line:
        :return:
        """
        self.code.extend([" " * self.indent_level, line, '\n'])

    INDENT_STEP = 4  # PEP8 says so

    def indent(self):
        """Increase the current indent for following lines."""
        self.indent_level += self.INDENT_STEP

    def dedent(self):
        """Decrease the current indent for following line. """
        self.indent_level -= self.INDENT_STEP

    def add_section(self):
        """Add a section, a sub-CodeBuilder."""
        section = CodeBuilder(self.indent_level)
        self.code.append(section)
        return section

    def __str__(self):
        return "".join(str(c) for c in self.code)

    def get_globals(self):
        """Execute the code, and return a dict of globals it defines."""
        # A check that the caller really finished all the blocks they started.
        assert self.indent_level == 0
        # Get the Python source as a single string.
        python_source = str(self)
        # Execute the source, defining globals, and return them.
        global_namespace = {}
        exec(python_source, global_namespace)
        return global_namespace


class TempliteSyntaxError(Exception):
    def __int__(self):
        Exception.__init__(self)


class Templite(object):
    def __init__(self, text, *contexts):
        """
        Construct a Templite with the given `text`.

        `contexts` are dictionaries of values to use for future renderings.
        These are good for filters and global values.
        :param text:
        :param contexts:
        """
        self.context = {}
        for context in contexts:
            self.context.update(context)
        self.all_vars = set()
        self.loop_vars = set()

        code = CodeBuilder()

        code.add_line("def render_function(context, do_dots):")
        code.indent()
        vars_code = code.add_section()
        code.add_line("result = []")
        code.add_line("append_result = result.append")
        code.add_line("extend_result = result.extend")
        code.add_line("to_str = str")

        buffered = []

        def flush_output():
            """Force `buffered` to the code builder."""
            if len(buffered) == 1:
                code.add_line("append_result(%s)" % buffered[0])
            elif len(buffered) > 1:
                code.add_line("extend_result([%s])" % ", ".join(buffered))
            del buffered[:]

        ops_stack = []
        """
        test example
        input: <p>Topics for {{name}}: {% for t in topics %}{{t}}, {% endfor %}</p>
        output:
            [
        '<p>Topics for ',               # literal
        '{{name}}',                     # expression
        ': ',                           # literal
        '{% for t in topics %}',        # tag
        '',                             # literal (empty)
        '{{t}}',                        # expression
        ', ',                           # literal
        '{% endfor %}',                 # tag
        '</p>'                          # literal
    ]
        """
        tokens = re.split(r"(?s)({{.*?}}|{%.*?%}|{#.*?#})", text)
        for token in tokens:
            if token.startswith('{#'):
                # comment line
                continue
            # The _expr_code method will compile the template expression into a Python expression.
            elif token.startswith('{{'):
                expr = self._expr_code(token[2:-2].strip())
                buffered.append('to_str({})'.format(expr))
            elif token.startswith('{%'):
                flush_output()
                words = token[2:-2].strip().split()
                # Analysis three sub-cases, based on the first word in the tag: if, for, or end
                if words[0] == 'if':
                    # An if statement: evaluate the expression to determine if.
                    if len(words) != 2:
                        self._syntax_error("Don't understand if", token)
                    ops_stack.append('if')
                    code.add_line("if %s:" % self._expr_code(words[1]))
                    code.indent()
                elif words[0] == 'for':
                    # A loop: iterate over expression result.
                    if len(words) != 4 or words[2] != 'in':
                        self._syntax_error("Don't understand for", token)
                    ops_stack.append('for')
                    self._variable(words[1], self.loop_vars)
                    code.add_line(
                        "for c_%s in %s:" % (
                            words[1],
                            self._expr_code(words[3])
                        )
                    )
                    code.indent()
                elif words[0].startswith('end'):
                    # Endsomething.  Pop the ops stack.
                    if len(words) != 1:
                        self._syntax_error("Don't understand end", token)
                    end_what = words[0][3:]
                    if not ops_stack:
                        self._syntax_error("Too many ends", token)
                    start_what = ops_stack.pop()
                    if start_what != end_what:
                        self._syntax_error("Mismatched end tag", end_what)
                    code.dedent()
                else:
                    self._syntax_error("Don't understand tag", words[0])
            else:
                # Literal content.  If not empty, output it.
                if token:
                    buffered.append(repr(token))
        if ops_stack:
            self._syntax_error("Unmatched action tag", ops_stack[-1])

        flush_output()

        for var_name in self.all_vars - self.loop_vars:
            vars_code.add_line("c_%s = context[%r]" % (var_name, var_name))
        code.add_line("return ''.join(result)")
        code.dedent()
        self._render_function = code.get_globals()['render_function']

    def _variable(self, name, vars_set):
        """Track that `name` is used as a variable.

        Adds the name to `vars_set`, a set of variable names.

        Raises an syntax error if `name` is not a valid name.

        """
        if not re.match(r"[_a-zA-Z][_a-zA-Z0-9]*$", name):
            self._syntax_error("Not a valid name", name)
        vars_set.add(name)

    def _syntax_error(self, msg, obj):
        raise TempliteSyntaxError("%s: %r" % (msg, obj))

    def _expr_code(self, expr):
        """Generate a Python expression for `expr`."""
        if '|' in expr:
            pipes = expr.split('|')
            code = pipes[0]
            for func in pipes[1:]:
                self._variable(func, self.all_vars)
                code = "c_{}({})".format(func, code)
        elif "." in expr:
            dots = expr.split(".")
            code = self._expr_code(dots[0])
            args = ", ".join(repr(d) for d in dots[1:])
            code = "do_dots(%s, %s)" % (code, args)
        else:
            self._variable(expr, self.all_vars)
            code = "c_%s" % expr
        return code

    def render(self, context=None):
        render_context = dict(self.context)
        if context:
            render_context.update(context)
        return self._render_function(render_context, self._do_dots)

    def _do_dots(self, value, *dots):
        """Evaluate dotted expressions at runtime."""
        for dot in dots:
            try:
                value = getattr(value, dot)
            except AttributeError:
                value = value[dot]
            if callable(value):
                value = value()
        return value


temp = """
<p>Topics for {{name}}: {% for t in topics %}{{t}}, {% endfor %}</p>
"""

a = Templite(temp)
rlt = a.render({'name': 'oyj', 'topics': ['a', 'b']})
print(rlt)
