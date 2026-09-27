from blokus.pieces import PIECE_NAMES, PIECES, TOTAL_SQUARES, drawing, normalize, piece_for_shape

EXPECTED_ORIENTATIONS = {
    "I1": 1,
    "I2": 2,
    "I3": 2,
    "V3": 4,
    "I4": 2,
    "L4": 8,
    "T4": 4,
    "O4": 1,
    "Z4": 4,
    "I5": 2,
    "L5": 8,
    "Y5": 8,
    "N5": 8,
    "P5": 8,
    "U5": 4,
    "V5": 4,
    "W5": 4,
    "Z5": 4,
    "T5": 4,
    "F5": 8,
    "X5": 1,
}


def test_catalog_has_the_standard_21_pieces():
    assert list(PIECE_NAMES) == list(EXPECTED_ORIENTATIONS)
    assert TOTAL_SQUARES == 89
    assert {name: len(p.orientations) for name, p in PIECES.items()} == EXPECTED_ORIENTATIONS
    assert sum(len(p.orientations) for p in PIECES.values()) == 91


def test_orientations_are_normalized_distinct_and_the_same_size():
    for piece in PIECES.values():
        assert len(set(piece.orientations)) == len(piece.orientations)
        assert piece.shape in piece.orientations
        for shape in piece.orientations:
            assert normalize(shape) == shape
            assert len(shape) == piece.size


def test_normalize_translates_to_the_origin_and_sorts():
    assert normalize([(7, 5), (5, 6), (6, 5)]) == ((0, 1), (1, 0), (2, 0))


def test_every_orientation_maps_back_to_its_piece():
    for piece in PIECES.values():
        for shape in piece.orientations:
            shifted = [(r + 3, c + 11) for r, c in shape]
            assert piece_for_shape(shifted) == piece.name


def test_non_pieces_are_not_recognized():
    assert piece_for_shape([(0, 0), (1, 1)]) is None  # diagonal, not connected
    assert piece_for_shape([(0, c) for c in range(6)]) is None  # too long


def test_drawing():
    assert drawing(PIECES["F5"].shape) == ".XX\nXX.\n.X."
    assert drawing(PIECES["I1"].shape) == "X"
