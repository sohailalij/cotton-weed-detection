from weedlab.split import assign_groups, group_of


def test_group_of() -> None:
    stem = "20210712_iPhoneSE_YL_218"
    assert group_of(stem) == "20210712"
    assert group_of(stem, "date_device") == "20210712_iPhoneSE"


def test_assignment_is_deterministic() -> None:
    vectors = [[10, 5, 5], [20, 10, 10], [15, 7, 8], [5, 2, 3], [30, 15, 15], [8, 4, 4]]
    a1, _ = assign_groups(vectors, [0.6, 0.2, 0.2], seed=1, restarts=20, min_per_class=0)
    a2, _ = assign_groups(vectors, [0.6, 0.2, 0.2], seed=1, restarts=20, min_per_class=0)
    assert a1 == a2
    assert len(a1) == len(vectors)
    assert all(s in (0, 1, 2) for s in a1)
