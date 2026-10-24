"""Pygments palette read from Figma THE IMAGE's JetBrains Mono code sample."""
from pygments.style import Style
from pygments.token import Token, Text, Whitespace, Keyword, Name, Number, String, Comment, Operator, Punctuation


class FigmaCodeStyle(Style):
    background_color = "#FBF5F2"
    default_style = ""
    styles = {
        Token: "#000000", Text: "#000000", Whitespace: "#000000",
        Keyword: "#E45E7F", Keyword.Constant: "#BE9931",
        Name: "#000000", Name.Builtin: "#3186E1", Name.Function: "#3186E1",
        Number: "#BE9931", String: "#BE9931", Comment: "#9D8084",
        Operator: "#000000", Operator.Word: "#E45E7F", Punctuation: "#000000",
    }
