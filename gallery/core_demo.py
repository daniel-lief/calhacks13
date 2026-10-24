from animai import *


class CoreDemo(AnimaiScene):
    def construct(self):
        theme = get_theme()
        with self.voiceover("Animai builds on 3Blue1Brown's engine, for every subject."):
            self.title_card("Animai", "Educational animation for any subject")
        self.fade_out_all()

        with self.voiceover("Regions keep things from piling up on screen."):
            self.set_title("Core building blocks")
            bullets = BulletList("Themes and layout regions", "Narration with captions",
                                 "Cards, callouts and code")
            self.place(bullets, "left")
            self.show(bullets, "left", animation=bullets.reveal())
            card = Card(Label("Every component follows the active theme.", size="small",
                              max_width=4.8), title="Note")
            self.show(card, "right")

        with self.voiceover("Showing something new in a region replaces what was there."):
            code = CodeBlock("def fib(n):\n    if n < 2:\n        return n\n"
                             "    return fib(n - 1) + fib(n - 2)")
            self.show(code, "right")
            self.play(code.highlight_line(2))
            self.play(code.highlight_line(4))

        with self.voiceover("Quotes and callouts help with history and diagrams."):
            quote = QuoteCard("The important thing is not to stop questioning.",
                              "Albert Einstein", "1955")
            self.show(quote, "main")
            self.play(FadeIn(Callout(quote.attribution, "Primary source", direction=DL)))
        self.wait()
