class Node:
    def __init__(self, data):
        self.data = data
        self.left = None
        self.right = None


def iterativePreorder(root):
    if root is None:
        return

    nodeStack = []
    nodeStack.append(root)

    while len(nodeStack) > 0:
        node = nodeStack.pop()
        print(node.data)

        if node.right is not None:
            nodeStack.append(node.right)

        if node.left is not None:
            nodeStack.append(node.left)


""" Constructed binary tree is
            1
          /   \
         2     3
        / \   / \ 
       4   5 6   7
"""


root = Node(1)
root.left = Node(2)
root.right = Node(3)
root.left.left = Node(4)
root.left.right = Node(5)
root.right.left = Node(6)
root.right.right = Node(7)

iterativePreorder(root)
