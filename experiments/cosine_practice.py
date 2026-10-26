from math import sqrt

a = [1, 0]
b = [1, 1]

dot_product = sum(x * y for x, y in zip(a, b))
length_a = sqrt(sum(x * x for x in a))
length_b = sqrt(sum(y * y for y in b))

# Your turn: replace ... with the calculation described above.
similarity = dot_product / (length_a * length_b)
print("Cosine similarity:", similarity)