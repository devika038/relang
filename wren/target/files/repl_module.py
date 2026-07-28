"""Ported from repl.h, repl.c, and repl.wren.

repl.c/repl.h were nearly empty in the original -- the whole REPL is
implemented in Wren itself (repl.wren), which the C side just loads and
runs. That means this file is the real port of repl.wren's ~950 lines:
`Repl`, `SimpleRepl`, `AnsiRepl`, the `Lexer`/`Token`/`Chars` tokenizer used
for syntax highlighting and completion, and the ANSI `Color` table.

One deliberate behavior change, unavoidable outside a Wren VM: the original
REPL compiles and runs each line as *Wren* source via `Meta.compile` /
`Meta.compileExpression` and a Wren `Fiber`. This port compiles and runs
each line as *Python* source via `compile()` / `exec()` / `eval()` instead,
since there is no Wren interpreter here. Line editing, history, cursor
movement, raw-mode ANSI redraw, and tab completion are all ported as
directly as possible.
"""

import sys

from io_module import Stdin, Stdout
from os_module import Platform


class Color:
    """ANSI color escape sequences. Ported from `Color` in repl.wren."""

    none = "\x1b[0m"
    black = "\x1b[30m"
    red = "\x1b[31m"
    green = "\x1b[32m"
    yellow = "\x1b[33m"
    blue = "\x1b[34m"
    magenta = "\x1b[35m"
    cyan = "\x1b[36m"
    white = "\x1b[37m"

    gray = "\x1b[30;1m"
    pink = "\x1b[31;1m"
    bright_white = "\x1b[37;1m"


class Chars:
    """Utilities for working with characters. Ported from `Chars` in
    repl.wren.
    """

    ctrl_a = 0x01
    ctrl_b = 0x02
    ctrl_c = 0x03
    ctrl_d = 0x04
    ctrl_e = 0x05
    ctrl_f = 0x06
    tab = 0x09
    line_feed = 0x0a
    ctrl_k = 0x0b
    ctrl_l = 0x0c
    carriage_return = 0x0d
    ctrl_n = 0x0e
    ctrl_p = 0x10
    ctrl_u = 0x15
    ctrl_w = 0x17
    escape = 0x1b
    space = 0x20
    bang = 0x21
    quote = 0x22
    percent = 0x25
    amp = 0x26
    left_paren = 0x28
    right_paren = 0x29
    star = 0x2a
    plus = 0x2b
    comma = 0x2c
    minus = 0x2d
    dot = 0x2e
    slash = 0x2f

    zero = 0x30
    nine = 0x39

    colon = 0x3a
    less = 0x3c
    equal = 0x3d
    greater = 0x3e
    question = 0x3f

    upper_a = 0x41
    upper_f = 0x46
    upper_z = 0x5a

    left_bracket = 0x5b
    backslash = 0x5c
    right_bracket = 0x5d
    caret = 0x5e
    underscore = 0x5f

    lower_a = 0x61
    lower_f = 0x66
    lower_x = 0x78
    lower_z = 0x7a

    left_brace = 0x7b
    pipe = 0x7c
    right_brace = 0x7d
    tilde = 0x7e
    delete = 0x7f

    @staticmethod
    def is_alpha(c):
        return (Chars.lower_a <= c <= Chars.lower_z or
                Chars.upper_a <= c <= Chars.upper_z or
                c == Chars.underscore)

    @staticmethod
    def is_digit(c):
        return Chars.zero <= c <= Chars.nine

    @staticmethod
    def is_alpha_numeric(c):
        return Chars.is_alpha(c) or Chars.is_digit(c)

    @staticmethod
    def is_hex_digit(c):
        return (Chars.zero <= c <= Chars.nine or
                Chars.lower_a <= c <= Chars.lower_f or
                Chars.upper_a <= c <= Chars.upper_f)

    @staticmethod
    def is_lower_alpha(c):
        return Chars.lower_a <= c <= Chars.lower_z

    @staticmethod
    def is_whitespace(c):
        return c in (Chars.space, Chars.tab, Chars.carriage_return)


class EscapeBracket:
    """Ported from `EscapeBracket` in repl.wren."""

    delete = 0x33
    up = 0x41
    down = 0x42
    right = 0x43
    left = 0x44
    end = 0x46
    home = 0x48


class Token:
    """Ported from `Token` in repl.wren."""

    # Punctuators.
    left_paren = "leftParen"
    right_paren = "rightParen"
    left_bracket = "leftBracket"
    right_bracket = "rightBracket"
    left_brace = "leftBrace"
    right_brace = "rightBrace"
    colon = "colon"
    dot = "dot"
    dot_dot = "dotDot"
    dot_dot_dot = "dotDotDot"
    comma = "comma"
    star = "star"
    slash = "slash"
    percent = "percent"
    plus = "plus"
    minus = "minus"
    pipe = "pipe"
    pipe_pipe = "pipePipe"
    caret = "caret"
    amp = "amp"
    amp_amp = "ampAmp"
    question = "question"
    bang = "bang"
    tilde = "tilde"
    equal = "equal"
    less = "less"
    less_equal = "lessEqual"
    less_less = "lessLess"
    greater = "greater"
    greater_equal = "greaterEqual"
    greater_greater = "greaterGreater"
    equal_equal = "equalEqual"
    bang_equal = "bangEqual"

    # Keywords.
    break_keyword = "break"
    class_keyword = "class"
    construct_keyword = "construct"
    else_keyword = "else"
    false_keyword = "false"
    for_keyword = "for"
    foreign_keyword = "foreign"
    if_keyword = "if"
    import_keyword = "import"
    in_keyword = "in"
    is_keyword = "is"
    null_keyword = "null"
    return_keyword = "return"
    static_keyword = "static"
    super_keyword = "super"
    this_keyword = "this"
    true_keyword = "true"
    var_keyword = "var"
    while_keyword = "while"

    field = "field"
    name = "name"
    number = "number"
    string = "string"
    interpolation = "interpolation"
    comment = "comment"
    whitespace = "whitespace"
    line = "line"
    error = "error"
    eof = "eof"

    def __init__(self, source, type_, start, length):
        # Originally: construct new(source, type, start, length).
        self._source = source
        self.type = type_
        self.start = start
        self.length = length

    @property
    def text(self):
        return self._source[self.start:self.start + self.length]

    def __str__(self):
        # Originally: `toString { text }`.
        return self.text


# Originally: `var KEYWORDS = {...}` in repl.wren.
KEYWORDS = {
    "break": Token.break_keyword,
    "class": Token.class_keyword,
    "construct": Token.construct_keyword,
    "else": Token.else_keyword,
    "false": Token.false_keyword,
    "for": Token.for_keyword,
    "foreign": Token.foreign_keyword,
    "if": Token.if_keyword,
    "import": Token.import_keyword,
    "in": Token.in_keyword,
    "is": Token.is_keyword,
    "null": Token.null_keyword,
    "return": Token.return_keyword,
    "static": Token.static_keyword,
    "super": Token.super_keyword,
    "this": Token.this_keyword,
    "true": Token.true_keyword,
    "var": Token.var_keyword,
    "while": Token.while_keyword,
}

# Originally: `var TOKEN_COLORS = {...}` in repl.wren.
TOKEN_COLORS = {
    Token.left_paren: Color.gray,
    Token.right_paren: Color.gray,
    Token.left_bracket: Color.gray,
    Token.right_bracket: Color.gray,
    Token.left_brace: Color.gray,
    Token.right_brace: Color.gray,
    Token.colon: Color.gray,
    Token.dot: Color.gray,
    Token.dot_dot: Color.none,
    Token.dot_dot_dot: Color.none,
    Token.comma: Color.gray,
    Token.star: Color.none,
    Token.slash: Color.none,
    Token.percent: Color.none,
    Token.plus: Color.none,
    Token.minus: Color.none,
    Token.pipe: Color.none,
    Token.pipe_pipe: Color.none,
    Token.caret: Color.none,
    Token.amp: Color.none,
    Token.amp_amp: Color.none,
    Token.question: Color.none,
    Token.bang: Color.none,
    Token.tilde: Color.none,
    Token.equal: Color.none,
    Token.less: Color.none,
    Token.less_equal: Color.none,
    Token.less_less: Color.none,
    Token.greater: Color.none,
    Token.greater_equal: Color.none,
    Token.greater_greater: Color.none,
    Token.equal_equal: Color.none,
    Token.bang_equal: Color.none,

    Token.break_keyword: Color.cyan,
    Token.class_keyword: Color.cyan,
    Token.construct_keyword: Color.cyan,
    Token.else_keyword: Color.cyan,
    Token.false_keyword: Color.cyan,
    Token.for_keyword: Color.cyan,
    Token.foreign_keyword: Color.cyan,
    Token.if_keyword: Color.cyan,
    Token.import_keyword: Color.cyan,
    Token.in_keyword: Color.cyan,
    Token.is_keyword: Color.cyan,
    Token.null_keyword: Color.cyan,
    Token.return_keyword: Color.cyan,
    Token.static_keyword: Color.cyan,
    Token.super_keyword: Color.cyan,
    Token.this_keyword: Color.cyan,
    Token.true_keyword: Color.cyan,
    Token.var_keyword: Color.cyan,
    Token.while_keyword: Color.cyan,

    Token.field: Color.none,
    Token.name: Color.none,
    Token.number: Color.magenta,
    Token.string: Color.yellow,
    Token.interpolation: Color.yellow,
    Token.comment: Color.gray,
    Token.whitespace: Color.none,
    Token.line: Color.none,
    Token.error: Color.red,
    Token.eof: Color.none,
}

# Data table for tokens that are tokenized using maximal munch. Ported from
# `PUNCTUATORS` in repl.wren.
#
# The key is the character that starts the token or tokens. After that is a
# list of token types and characters. As long as the next character is
# matched, the type will update to the type after that character.
PUNCTUATORS = {
    Chars.left_paren: [Token.left_paren],
    Chars.right_paren: [Token.right_paren],
    Chars.left_bracket: [Token.left_bracket],
    Chars.right_bracket: [Token.right_bracket],
    Chars.left_brace: [Token.left_brace],
    Chars.right_brace: [Token.right_brace],
    Chars.colon: [Token.colon],
    Chars.comma: [Token.comma],
    Chars.star: [Token.star],
    Chars.percent: [Token.percent],
    Chars.plus: [Token.plus],
    Chars.minus: [Token.minus],
    Chars.tilde: [Token.tilde],
    Chars.caret: [Token.caret],
    Chars.question: [Token.question],
    Chars.line_feed: [Token.line],

    Chars.pipe: [Token.pipe, Chars.pipe, Token.pipe_pipe],
    Chars.amp: [Token.amp, Chars.amp, Token.amp_amp],
    Chars.bang: [Token.bang, Chars.equal, Token.bang_equal],
    Chars.equal: [Token.equal, Chars.equal, Token.equal_equal],

    Chars.dot: [Token.dot, Chars.dot, Token.dot_dot, Chars.dot, Token.dot_dot_dot],
}


class Lexer:
    """Tokenizes a string of input. Ported from `Lexer` in repl.wren.

    This lexer differs from most in that it silently ignores errors from
    incomplete input, like a string literal with no closing quote. That's
    because this is intended to be run on a line of input while the user is
    still typing it.
    """

    def __init__(self, source):
        # Originally: construct new(source).
        self._source = source
        # Due to the magic of UTF-8, the original safely treats source as a
        # series of bytes. Same here.
        self._bytes = source.encode("utf-8")
        self._start = 0
        self._current = 0
        # The stack of ongoing interpolated strings. Each element is the
        # number of unbalanced "(" still remaining to be closed.
        self._interpolations = []

    def read_token(self):
        if self._current >= len(self._bytes):
            return self._make_token(Token.eof)

        self._start = self._current
        c = self._bytes[self._current]
        self._advance()

        if self._interpolations:
            if c == Chars.left_paren:
                self._interpolations[-1] += 1
            elif c == Chars.right_paren:
                self._interpolations[-1] -= 1
                if self._interpolations[-1] == 0:
                    self._interpolations.pop()
                    return self._read_string()

        if c in PUNCTUATORS:
            punctuator = PUNCTUATORS[c]
            type_ = punctuator[0]
            i = 1
            while i < len(punctuator):
                if not self._match(punctuator[i]):
                    break
                type_ = punctuator[i + 1]
                i += 2
            return self._make_token(type_)

        # Handle "<", "<<", and "<=".
        if c == Chars.less:
            if self._match(Chars.less):
                return self._make_token(Token.less_less)
            if self._match(Chars.equal):
                return self._make_token(Token.less_equal)
            return self._make_token(Token.less)

        # Handle ">", ">>", and ">=".
        if c == Chars.greater:
            if self._match(Chars.greater):
                return self._make_token(Token.greater_greater)
            if self._match(Chars.equal):
                return self._make_token(Token.greater_equal)
            return self._make_token(Token.greater)

        # Handle "/", "//", and "/*".
        if c == Chars.slash:
            if self._match(Chars.slash):
                return self._read_line_comment()
            if self._match(Chars.star):
                return self._read_block_comment()
            return self._make_token(Token.slash)

        if c == Chars.underscore:
            return self._read_field()
        if c == Chars.quote:
            return self._read_string()

        if c == Chars.zero and self._peek() == Chars.lower_x:
            return self._read_hex_number()
        if Chars.is_whitespace(c):
            return self._read_whitespace()
        if Chars.is_digit(c):
            return self._read_number()
        if Chars.is_alpha(c):
            return self._read_name()

        return self._make_token(Token.error)

    def _read_line_comment(self):
        while self._peek() != Chars.line_feed and not self._is_at_end():
            self._advance()
        return self._make_token(Token.comment)

    def _read_block_comment(self):
        nesting = 1
        while nesting > 0:
            # TODO: Report error.
            if self._is_at_end():
                break

            if self._peek() == Chars.slash and self._peek(1) == Chars.star:
                self._advance()
                self._advance()
                nesting += 1
            elif self._peek() == Chars.star and self._peek(1) == Chars.slash:
                self._advance()
                self._advance()
                nesting -= 1
                if nesting == 0:
                    break
            else:
                self._advance()
        return self._make_token(Token.comment)

    def _read_field(self):
        while self._match(Chars.is_alpha_numeric):
            pass
        return self._make_token(Token.field)

    def _read_string(self):
        type_ = Token.string
        while not self._is_at_end():
            c = self._bytes[self._current]
            self._advance()

            if c == Chars.backslash:
                # TODO: Process specific escapes and validate them.
                if not self._is_at_end():
                    self._advance()
            elif c == Chars.percent:
                if not self._is_at_end():
                    self._advance()
                # TODO: Handle missing '('.
                self._interpolations.append(1)
                type_ = Token.interpolation
                break
            elif c == Chars.quote:
                break
        return self._make_token(type_)

    def _read_hex_number(self):
        # Skip past the `x`.
        self._advance()
        while self._match(Chars.is_hex_digit):
            pass
        return self._make_token(Token.number)

    def _read_whitespace(self):
        while self._match(Chars.is_whitespace):
            pass
        return self._make_token(Token.whitespace)

    def _read_number(self):
        # TODO: Floating point, scientific.
        while self._match(Chars.is_digit):
            pass
        return self._make_token(Token.number)

    def _read_name(self):
        while self._match(Chars.is_alpha_numeric):
            pass
        text = self._source[self._start:self._current]
        type_ = KEYWORDS.get(text, Token.name)
        return Token(self._source, type_, self._start, self._current - self._start)

    def _is_at_end(self):
        return self._current >= len(self._bytes)

    def _advance(self):
        self._current += 1

    def _peek(self, n=0):
        if self._current + n >= len(self._bytes):
            return -1
        return self._bytes[self._current + n]

    def _match(self, condition):
        if self._is_at_end():
            return False

        c = self._bytes[self._current]
        if callable(condition):
            if not condition(c):
                return False
        elif c != condition:
            return False

        self._advance()
        return True

    def _make_token(self, type_):
        return Token(self._source, type_, self._start, self._current - self._start)


# Token types that make `_execute_input` treat the line as a statement
# rather than an expression. Ported from the `isStatement` check inside
# `executeInput()` in repl.wren.
_STATEMENT_TOKEN_TYPES = {
    Token.break_keyword, Token.class_keyword, Token.for_keyword,
    Token.foreign_keyword, Token.if_keyword, Token.import_keyword,
    Token.return_keyword, Token.var_keyword, Token.while_keyword,
}


class Repl:
    """Abstract base class for the REPL. Ported from `Repl` in repl.wren.

    Manages the input line and history, but does not render.
    """

    def __init__(self):
        # Originally: construct new().
        self.cursor = 0
        self.line = ""

        self._history = []
        self._history_index = 0

        # Evaluated top-level names, so `var`s and `def`s from one line stay
        # visible to later lines -- the Python-eval equivalent of Wren's
        # persistent module-level state, and also used by getCompletion().
        self._globals = {"__name__": "__repl__"}

    def run(self):
        Stdin.set_raw(True)
        self.refresh_line(False)

        while True:
            byte = Stdin.read_byte()
            if byte is None or self.handle_char(byte):
                break
            self.refresh_line(True)

    def handle_char(self, byte):
        if byte == Chars.ctrl_c:
            print()
            return True
        elif byte == Chars.ctrl_d:
            # If the line is empty, Ctrl-D exits.
            if not self.line:
                print()
                return True
            # Otherwise, it deletes the character after the cursor.
            self._delete_right()
        elif byte == Chars.tab:
            completion = self._get_completion()
            if completion is not None:
                self.line = self.line + completion
                self.cursor = len(self.line)
        elif byte == Chars.ctrl_u:
            # Clear the line.
            self.line = ""
            self.cursor = 0
        elif byte == Chars.ctrl_n:
            self._next_history()
        elif byte == Chars.ctrl_p:
            self._previous_history()
        elif byte == Chars.escape:
            escape_type = Stdin.read_byte()
            value = Stdin.read_byte()
            if escape_type == Chars.left_bracket:
                # ESC [ sequence.
                self.handle_escape_bracket(value)
            # else: TODO: Handle ESC 0 sequences.
        elif byte == Chars.carriage_return:
            self._execute_input()
        elif byte == Chars.delete:
            self._delete_left()
        elif Chars.space <= byte <= Chars.tilde:
            self._insert_char(byte)
        elif byte == Chars.ctrl_w:
            # Delete trailing spaces.
            while self.cursor != 0 and self.line[self.cursor - 1] == " ":
                self._delete_left()
            # Delete until the next space.
            while self.cursor != 0 and self.line[self.cursor - 1] != " ":
                self._delete_left()
        else:
            # TODO: Other shortcuts?
            print(f"Unhandled key-code [dec]: {byte}")

        return False

    def _insert_char(self, byte):
        """Inserts the character with [byte] value at the current cursor
        position."""
        char = chr(byte)
        self.line = self.line[:self.cursor] + char + self.line[self.cursor:]
        self.cursor += 1

    def _delete_left(self):
        """Deletes the character before the cursor, if any."""
        if self.cursor == 0:
            return
        self.line = self.line[:self.cursor - 1] + self.line[self.cursor:]
        self.cursor -= 1

    def _delete_right(self):
        """Deletes the character after the cursor, if any."""
        if self.cursor == len(self.line):
            return
        self.line = self.line[:self.cursor] + self.line[self.cursor + 1:]

    def handle_escape_bracket(self, byte):
        if byte == EscapeBracket.up:
            self._previous_history()
        elif byte == EscapeBracket.down:
            self._next_history()
        elif byte == EscapeBracket.delete:
            self._delete_right()
            # Consume extra 126 character generated by delete.
            Stdin.read_byte()
        elif byte == EscapeBracket.end:
            self.cursor = len(self.line)
        elif byte == EscapeBracket.home:
            self.cursor = 0

    def _previous_history(self):
        if self._history_index == 0:
            return
        self._history_index -= 1
        self.line = self._history[self._history_index]
        self.cursor = len(self.line)

    def _next_history(self):
        if self._history_index >= len(self._history):
            return
        self._history_index += 1
        if self._history_index < len(self._history):
            self.line = self._history[self._history_index]
            self.cursor = len(self.line)
        else:
            self.line = ""
            self.cursor = 0

    def _execute_input(self):
        # Remove the completion hint.
        self.refresh_line(False)

        # Add it to the history (if the line is interesting).
        if self.line != "" and (not self._history or self._history[-1] != self.line):
            self._history.append(self.line)
            self._history_index = len(self._history)

        # Reset the current line.
        input_line = self.line
        self.line = ""
        self.cursor = 0

        print()

        # Guess if it looks like a statement or expression. If it looks like
        # an expression, we try to print the result.
        token = self._lex_first(input_line)

        # No code, so do nothing.
        if token is None:
            return

        is_statement = token.type in _STATEMENT_TOKEN_TYPES

        # Originally: `closure = Meta.compile(input)` /
        # `closure = Meta.compileExpression(input)`. There's no Wren VM
        # here, so this compiles Python source instead. Wren requires a
        # leading `var` keyword for assignment, so the leading-token guess
        # above is reliable there; Python assignment (`x = 1`) has no such
        # keyword, so if the guessed mode fails to compile, retry as the
        # other mode before giving up.
        try:
            if is_statement:
                code = compile(input_line, "<repl>", "exec")
            else:
                code = compile(input_line, "<repl>", "eval")
        except SyntaxError:
            try:
                is_statement = not is_statement
                if is_statement:
                    code = compile(input_line, "<repl>", "exec")
                else:
                    code = compile(input_line, "<repl>", "eval")
            except SyntaxError as error:
                # Stop if there was a compile error.
                self.show_runtime_error(f"Compile error: {error}")
                return

        # Originally: runs the compiled closure on a new Fiber and checks
        # `fiber.error`.
        try:
            if is_statement:
                exec(code, self._globals)
            else:
                result = eval(code, self._globals)
                self.show_result(result)
        except Exception as error:  # noqa: BLE001 - mirrors catching any fiber error
            # TODO: Include callstack.
            self.show_runtime_error(f"Runtime error: {error}")

    def lex(self, line, include_whitespace):
        lexer = Lexer(line)
        tokens = []
        while True:
            token = lexer.read_token()
            if token.type == Token.eof:
                break
            if include_whitespace or token.type not in (Token.comment, Token.whitespace):
                tokens.append(token)
        return tokens

    def _lex_first(self, line):
        lexer = Lexer(line)
        while True:
            token = lexer.read_token()
            if token.type == Token.eof:
                return None
            if token.type not in (Token.comment, Token.whitespace):
                return token

    def _get_completion(self):
        """Gets the best possible auto-completion for the current line, or
        None if there is none. The completion is the remaining string to
        append to the line, not the entire completed line.
        """
        if not self.line:
            return None

        # Only complete if the cursor is at the end.
        if self.cursor != len(self.line):
            return None

        # Originally: `for (name in Meta.getModuleVariables("repl"))` --
        # completes against names defined so far in this REPL session.
        for name in list(self._globals.keys()):
            if name.startswith(self.line):
                return name[len(self.line):]
        return None

    # --- Overridden by subclasses. ---

    def refresh_line(self, show_completion):
        raise NotImplementedError

    def show_result(self, value):
        raise NotImplementedError

    def show_runtime_error(self, message):
        raise NotImplementedError


class SimpleRepl(Repl):
    """A reduced functionality REPL that doesn't use ANSI escape sequences.

    Ported from `SimpleRepl` in repl.wren.
    """

    def __init__(self):
        super().__init__()
        self._erase = ""

    def refresh_line(self, show_completion):
        # A carriage return just moves the cursor to the beginning of the
        # line. We have to erase it manually. Since we can't use ANSI
        # escapes, and we don't know how wide the terminal is, erase the
        # longest line we've seen so far.
        if len(self.line) > len(self._erase):
            self._erase = " " * len(self.line)
        sys.stdout.write("\r  " + self._erase)

        # Show the prompt at the beginning of the line.
        sys.stdout.write("\r> ")

        # Write the line.
        sys.stdout.write(self.line)
        Stdout.flush()

    def show_result(self, value):
        # TODO: Syntax color based on type? It might be nice to distinguish
        # between string results versus stringified results. Otherwise, the
        # user can't tell the difference between `True` and "True".
        print(value)

    def show_runtime_error(self, message):
        print(message)


class AnsiRepl(Repl):
    """Ported from `AnsiRepl` in repl.wren."""

    def __init__(self):
        super().__init__()

    def handle_char(self, byte):
        if byte == Chars.ctrl_a:
            self.cursor = 0
        elif byte == Chars.ctrl_b:
            self._cursor_left()
        elif byte == Chars.ctrl_e:
            self.cursor = len(self.line)
        elif byte == Chars.ctrl_f:
            self._cursor_right()
        elif byte == Chars.ctrl_k:
            # Delete everything after the cursor.
            self.line = self.line[:self.cursor]
        elif byte == Chars.ctrl_l:
            # Clear the screen.
            sys.stdout.write("\x1b[2J")
            # Move cursor to top left.
            sys.stdout.write("\x1b[H")
        else:
            # TODO: Ctrl-T to swap chars.
            # TODO: ESC H and F to move to beginning and end of line. (Both
            # ESC [ and ESC 0 sequences?)
            # TODO: Ctrl-W delete previous word.
            return super().handle_char(byte)

        return False

    def handle_escape_bracket(self, byte):
        if byte == EscapeBracket.left:
            self._cursor_left()
        elif byte == EscapeBracket.right:
            self._cursor_right()

        super().handle_escape_bracket(byte)

    def _cursor_left(self):
        """Move the cursor left one character."""
        if self.cursor > 0:
            self.cursor -= 1

    def _cursor_right(self):
        """Move the cursor right one character."""
        # TODO: Take into account multi-byte characters?
        if self.cursor < len(self.line):
            self.cursor += 1

    def refresh_line(self, show_completion):
        # Erase the whole line.
        sys.stdout.write("\x1b[2K")

        # Show the prompt at the beginning of the line.
        sys.stdout.write(Color.gray)
        sys.stdout.write("\r> ")
        sys.stdout.write(Color.none)

        # Syntax highlight the line.
        for token in self.lex(self.line, True):
            if token.type == Token.eof:
                break

            sys.stdout.write(TOKEN_COLORS.get(token.type, Color.none))
            sys.stdout.write(token.text)
            sys.stdout.write(Color.none)

        if show_completion:
            completion = self._get_completion()
            if completion is not None:
                sys.stdout.write(f"{Color.gray}{completion}{Color.none}")

        # Position the cursor.
        sys.stdout.write(f"\r\x1b[{2 + self.cursor}C")
        Stdout.flush()

    def show_result(self, value):
        # TODO: Syntax color based on type? It might be nice to distinguish
        # between string results versus stringified results.
        print(f"{Color.bright_white}{value!r}{Color.none}")

    def show_runtime_error(self, message):
        # TODO: Print entire stack.
        print(f"{Color.red}{message}{Color.none}")


def main():
    """Fire up the REPL. We use ANSI when talking to a POSIX TTY.

    Ported from the top-level code at the bottom of repl.wren:
        if (Platform.isPosix && Stdin.isTerminal) {
          AnsiRepl.new().run()
        } else {
          SimpleRepl.new().run()
        }
    """
    if Platform.is_posix() and Stdin.is_terminal():
        AnsiRepl().run()
    else:
        # ANSI escape sequences probably aren't supported, so degrade.
        SimpleRepl().run()


if __name__ == "__main__":
    main()
