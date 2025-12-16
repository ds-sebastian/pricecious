from app.services.item_service import ItemService


def test_effective_interval_logic():
    """
    Verify the priority: Item > Profile > Global
    """
    global_int = 60

    # Case 1: All defined -> Item wins
    assert ItemService._get_effective_interval(item_int=30, profile_int=120, global_int=global_int) == 30

    # Case 2: Item None, Profile defined -> Profile wins
    assert ItemService._get_effective_interval(item_int=None, profile_int=120, global_int=global_int) == 120

    # Case 3: Both None -> Global wins
    assert ItemService._get_effective_interval(item_int=None, profile_int=None, global_int=global_int) == 60

    # Case 4: Item explicitly shorter than global
    assert ItemService._get_effective_interval(item_int=5, profile_int=None, global_int=600) == 5

    # Case 5: Minimum clamp (should be at least 5 minutes)
    assert ItemService._get_effective_interval(item_int=1, profile_int=None, global_int=60) == 5
