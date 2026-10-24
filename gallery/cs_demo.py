from animai import *


class CSDemo(AnimaiScene):
    def construct(self):
        self.set_title("Bubble sort")
        arr = ArrayViz([5, 2, 8, 1, 4])
        self.show(arr, "main")
        i = arr.pointer(0, "i")
        self.play(FadeIn(i))
        self.play(arr.move_pointer(i, 3))
        self.play(FadeOut(i))
        arr.run_sort(self, "bubble", step_time=0.25)

        self.set_title("Stack and queue")
        stack = StackViz([1, 2])
        queue = QueueViz(["A", "B", "C"])
        self.show(stack, "left")
        self.show(queue, "right")
        self.play(stack.push(3))
        self.play(stack.pop())
        self.play(queue.enqueue("D"))
        self.play(queue.dequeue())

        self.set_title("Linked list")
        ll = LinkedListViz([3, 7, 1])
        self.show(ll, "main")
        self.play(ll.insert(1, 5))
        self.play(ll.remove_at(2))
        self.play(ll.traverse())

        self.set_title("Binary search tree")
        bst = BinaryTree([8, 3, 10, 1, 6, 14])
        self.show(bst, "main")
        self.play(bst.insert(7))
        self.play(bst.search(6))

        self.set_title("Dijkstra's algorithm")
        g = GraphViz([("A", "B", 4), ("A", "C", 2), ("C", "B", 1), ("B", "D", 5), ("C", "D", 8),
                      ("D", "E", 3), ("C", "E", 10)], weighted=True)
        self.show(g, "main")
        g.run_dijkstra(self, "A", target="E", step_time=0.3)

        self.set_title("Binary numbers")
        b = BinaryNumber(5, n_bits=8)
        self.show(b, "main")
        self.play(b.set_value(6))
        self.play(b.set_value(255))
        self.wait()
