"""
Verhoeff Checksum - Aadhaar UID validation.

Built on the dihedral group D5 (symmetry group of a regular pentagon).
Non-commutative structure catches transposition errors that sum-based
checksums miss.

References:
  - Verhoeff, J. (1969). Error Detecting Decimal Codes.
  - https://en.wikipedia.org/wiki/Verhoeff_algorithm
"""

# Multiplication table - encodes D5 group operation (10x10)
_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

# Permutation table - 8 permutations cycling through digit positions (8x10)
_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]

# Inverse table - additive inverse in D5
_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def verhoeff_validate(number: str) -> bool:
    """
    Validate a number string using the Verhoeff checksum.

    A valid number produces a running product of 0 when processed
    right-to-left through the multiplication and permutation tables.

    Args:
        number: Digit string (spaces/dashes stripped before calling).

    Returns:
        True if checksum is valid, False otherwise.
    """
    number = number.replace(" ", "").replace("-", "")
    if not number.isdigit() or len(number) != 12:
        return False

    c = 0
    for i, digit in enumerate(reversed(number)):
        c = _D[c][_P[i % 8][int(digit)]]
    return c == 0


def verhoeff_generate(number: str) -> str:
    """
    Append the correct Verhoeff check digit to a number string.

    Args:
        number: Digit string WITHOUT the check digit.

    Returns:
        Original number with check digit appended.
    """
    number = number.replace(" ", "").replace("-", "")
    c = 0
    for i, digit in enumerate(reversed(number)):
        c = _D[c][_P[(i + 1) % 8][int(digit)]]
    return number + str(_INV[c])
