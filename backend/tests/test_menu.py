"""Danh mục món gốc của nhà hàng + ràng buộc mỗi ngày chỉ 1 quán."""

from datetime import date, timedelta

from .conftest import login

FUTURE_DATE = (date.today() + timedelta(days=5)).isoformat()


def _second_restaurant(container):
    return container.restaurants.create({"name": "Quán B"})["id"]


def test_add_and_list_catalog_item(client, container):
    login(client)
    restaurant_id = container.restaurant_repo.list_all()[0].id

    resp = client.post(f"/api/admin/restaurants/{restaurant_id}/catalog", json={
        "name": "Cơm sườn", "price": 35000,
    })
    assert resp.status_code == 201

    resp = client.get(f"/api/admin/restaurants/{restaurant_id}/catalog")
    assert resp.status_code == 200
    names = [i["name"] for i in resp.get_json()["items"]]
    assert "Cơm sườn" in names


def test_delete_catalog_item(client, container):
    login(client)
    restaurant_id = container.restaurant_repo.list_all()[0].id
    catalog_id = client.post(f"/api/admin/restaurants/{restaurant_id}/catalog", json={
        "name": "Món xoá", "price": 20000,
    }).get_json()["id"]

    resp = client.delete(f"/api/admin/catalog/{catalog_id}")
    assert resp.status_code == 200

    items = client.get(f"/api/admin/restaurants/{restaurant_id}/catalog").get_json()["items"]
    assert all(i["id"] != catalog_id for i in items)


def test_apply_catalog_items_to_date(client, container):
    login(client)
    restaurant_id = container.restaurant_repo.list_all()[0].id
    catalog_id = client.post(f"/api/admin/restaurants/{restaurant_id}/catalog", json={
        "name": "Cơm gà", "price": 30000,
    }).get_json()["id"]

    resp = client.post("/api/admin/menu/from-catalog", json={
        "available_date": FUTURE_DATE, "restaurant_id": restaurant_id,
        "catalog_ids": [catalog_id],
    })
    assert resp.status_code == 200
    assert resp.get_json()["created"] == 1

    resp = client.get(f"/api/menu?date={FUTURE_DATE}")
    names = [i["name"] for i in resp.get_json()["items"]]
    assert "Cơm gà" in names


def test_applying_same_catalog_item_twice_skips_duplicate(client, container):
    login(client)
    restaurant_id = container.restaurant_repo.list_all()[0].id
    catalog_id = client.post(f"/api/admin/restaurants/{restaurant_id}/catalog", json={
        "name": "Bún chả", "price": 32000,
    }).get_json()["id"]

    client.post("/api/admin/menu/from-catalog", json={
        "available_date": FUTURE_DATE, "restaurant_id": restaurant_id,
        "catalog_ids": [catalog_id],
    })
    resp = client.post("/api/admin/menu/from-catalog", json={
        "available_date": FUTURE_DATE, "restaurant_id": restaurant_id,
        "catalog_ids": [catalog_id],
    })
    assert resp.status_code == 200
    assert resp.get_json()["created"] == 0
    assert "Bún chả" in resp.get_json()["skipped"]


def test_cannot_mix_two_restaurants_same_date(client, container):
    login(client)
    restaurant_a = container.restaurant_repo.list_all()[0].id
    restaurant_b = _second_restaurant(container)

    client.post("/api/admin/menu", json={
        "name": "Món A", "price": 25000,
        "available_date": FUTURE_DATE, "restaurant_id": restaurant_a,
    })

    resp = client.post("/api/admin/menu", json={
        "name": "Món B", "price": 25000,
        "available_date": FUTURE_DATE, "restaurant_id": restaurant_b,
    })
    assert resp.status_code == 400
    assert "1 quán" in resp.get_json()["error"]


def test_can_add_more_items_same_restaurant_same_date(client, container):
    login(client)
    restaurant_id = container.restaurant_repo.list_all()[0].id

    client.post("/api/admin/menu", json={
        "name": "Món 1", "price": 25000,
        "available_date": FUTURE_DATE, "restaurant_id": restaurant_id,
    })
    resp = client.post("/api/admin/menu", json={
        "name": "Món 2", "price": 25000,
        "available_date": FUTURE_DATE, "restaurant_id": restaurant_id,
    })
    assert resp.status_code == 201


def test_can_edit_item_untouched_when_date_has_legacy_mixed_restaurants(client, container):
    """Dữ liệu cũ (trước khi có ràng buộc DB) lỡ có 2 quán cùng ngày thì sửa
    tên/giá 1 món trên ngày đó (không đổi quán/ngày) vẫn phải chạy được — cả
    _assert_single_restaurant() (tầng service) lẫn 2 trigger (tầng DB) chỉ
    chặn khi THỰC SỰ đổi restaurant_id/available_date, không chặn oan món
    không liên quan tới nguyên nhân vi phạm."""
    login(client)
    restaurant_a = container.restaurant_repo.list_all()[0].id
    restaurant_b = _second_restaurant(container)

    # Mô phỏng dữ liệu cũ đã lỡ vi phạm bất biến TRƯỚC KHI có trigger — tắt
    # tạm 2 trigger, ghi thẳng qua repository, rồi bật lại đúng như lúc
    # init_schema() chạy tiếp theo sẽ tự làm (DROP rồi CREATE lại).
    from lunchapp.models import MenuItem

    with container.database.session(commit=True) as conn:
        conn.execute("DROP TRIGGER IF EXISTS trg_menu_items_single_restaurant_insert")
        conn.execute("DROP TRIGGER IF EXISTS trg_menu_items_single_restaurant_update")

    item_a_id = container.menu_items.create(MenuItem(
        name="Món cũ A", price=20000, available_date=FUTURE_DATE, restaurant_id=restaurant_a,
    ))
    container.menu_items.create(MenuItem(
        name="Món cũ B", price=20000, available_date=FUTURE_DATE, restaurant_id=restaurant_b,
    ))

    container.database.init_schema()

    resp = client.put(f"/api/admin/menu/{item_a_id}", json={
        "name": "Món cũ A (sửa tên)", "price": 22000,
        "available_date": FUTURE_DATE, "restaurant_id": restaurant_a,
    })
    assert resp.status_code == 200
