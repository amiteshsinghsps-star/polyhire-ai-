import os
def print_tree(startpath, exclude_dirs):
    lines = []
    for root, dirs, files in os.walk(startpath):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * (level)
        lines.append('{}{}/'.format(indent, os.path.basename(root)))
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            lines.append('{}{}'.format(subindent, f))
    return '\n'.join(lines)

tree = print_tree('.', set(['node_modules', '.git', '.turbo', 'dist', '__pycache__', '.pytest_cache', '.next']))
with open('tree.txt', 'w', encoding='utf-8') as f:
    f.write(tree)
