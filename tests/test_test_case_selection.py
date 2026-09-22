import pytest

from evalforge.database import SessionLocal
from evalforge.models import TestCase as StoredTestCase
from evalforge.services import select_test_cases


@pytest.fixture()
def selection_db():
    with SessionLocal() as db:
        db.add_all([
            StoredTestCase(id=identifier, question="Question?", expected_answer="Answer.")
            for identifier in ["first", "second"]
        ])
        db.commit()
        yield db


def test_none_selects_every_stored_case_in_stable_order(selection_db):
    assert [row.id for row in select_test_cases(selection_db)] == ["first", "second"]


def test_explicit_generator_selects_exact_subset(selection_db):
    assert [row.id for row in select_test_cases(selection_db, iter(["second"]))] == ["second"]


@pytest.mark.parametrize(
    "ids,message",
    [
        ([], "at least one ID"),
        (["first", "missing"], "Unknown test case IDs: missing"),
        (["missing"], "Unknown test case IDs: missing"),
        (["first", "first"], "must be unique"),
    ],
)
def test_explicit_selection_never_silently_changes_requested_cases(selection_db, ids, message):
    with pytest.raises(ValueError, match=message):
        select_test_cases(selection_db, iter(ids))
