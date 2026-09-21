"""
آزمون چیدمان قابل جابه‌جایی صفحات.

کاربر خواست بتواند ترتیب کارت‌های داشبورد را خودش تعیین کند. نکتهٔ حساس
این است که جابه‌جایی نباید محتوای کارت را از بین ببرد و چیدمان ذخیره‌شده
باید با افزودن کارت تازه در نسخه‌های بعدی هم کار کند.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem

from localization import Translator
from ui.widgets.arrangeable import HIDDEN_MARK, ArrangeableContainer


@pytest.fixture()
def container(qt_application) -> ArrangeableContainer:  # noqa: ARG001 - نیاز به QApplication
    """ظرفی با سه بخش نمونه."""
    box = ArrangeableContainer(Translator("fa"))
    for key in ("alpha", "beta", "gamma"):
        box.add_block(key, key.upper(), QLabel(key))
    return box


class TestOrdering:
    """جابه‌جایی بخش‌ها."""

    def test_initial_order_follows_insertion(self, container) -> None:
        """ترتیب اولیه همان ترتیب افزودن است."""
        assert container.order == ["alpha", "beta", "gamma"]

    def test_move_down_swaps_with_the_next_block(self, container) -> None:
        """جابه‌جایی به پایین باید فقط یک پله باشد."""
        assert container.move_down("alpha")

        assert container.order == ["beta", "alpha", "gamma"]

    def test_move_up_swaps_with_the_previous_block(self, container) -> None:
        """و به بالا هم همین‌طور."""
        assert container.move_up("gamma")

        assert container.order == ["alpha", "gamma", "beta"]

    def test_cannot_move_past_the_edges(self, container) -> None:
        """در ابتدا و انتها، جابه‌جایی باید بی‌اثر و بی‌خطا باشد."""
        assert not container.move_up("alpha")
        assert not container.move_down("gamma")
        assert container.order == ["alpha", "beta", "gamma"]

    def test_unknown_key_is_ignored(self, container) -> None:
        """درخواست برای بخشی که وجود ندارد نباید خطا بدهد."""
        assert not container.move_up("nope")

    def test_edge_buttons_are_disabled_at_the_ends(self, container) -> None:
        """دکمهٔ بی‌اثر نباید فعال بماند."""
        blocks = container.blocks

        assert not blocks["alpha"].up_button.isEnabled()
        assert not blocks["gamma"].down_button.isEnabled()
        assert blocks["beta"].up_button.isEnabled()

    def test_layout_widget_order_matches_logical_order(self, container) -> None:
        """ترتیب منطقی باید واقعاً روی صفحه هم دیده شود."""
        container.move_down("alpha")

        layout = container.layout()
        positions = {
            key: layout.indexOf(block) for key, block in container.blocks.items()
        }
        assert positions["beta"] < positions["alpha"] < positions["gamma"]

    def test_moving_preserves_widget_content(self, qt_application) -> None:  # noqa: ARG001
        """
        جابه‌جایی نباید داده را از بین ببرد.

        اگر کارت‌ها بازساخته می‌شدند، ردیف‌های جدول پاک می‌شد و کاربر با
        هر جابه‌جایی داده‌اش را از دست می‌داد.
        """
        box = ArrangeableContainer(Translator("fa"))
        table = QTableWidget(1, 1)
        table.setItem(0, 0, QTableWidgetItem("BTC/USDT"))
        box.add_block("table", "جدول", table)
        box.add_block("other", "دیگر", QLabel("x"))

        box.move_down("table")

        assert table.item(0, 0).text() == "BTC/USDT"
        assert box.blocks["table"].content is table


class TestVisibility:
    """پنهان و نمایان کردن بخش‌ها."""

    def test_hiding_a_block_hides_its_content(self, container) -> None:
        """پنهان‌کردن باید واقعاً محتوا را بردارد."""
        block = container.blocks["beta"]

        block.set_content_visible(False)

        assert not block.content_visible
        assert not block.content.isVisibleTo(container)

    def test_hidden_block_stays_reachable_in_arrange_mode(self, container) -> None:
        """
        بخش پنهان باید در حالت چیدمان دیده شود.

        وگرنه کاربر راهی برای برگرداندنش ندارد و کارت برای همیشه گم
        می‌شود.
        """
        block = container.blocks["beta"]
        block.set_content_visible(False)

        container.set_arrange_mode(True)

        assert block.isVisibleTo(container)
        assert block.bar.isVisibleTo(container)


class TestPersistence:
    """ذخیره و بازگردانی چیدمان."""

    def test_serialise_records_order_and_visibility(self, container) -> None:
        """یک رشته باید هر دو را نگه دارد."""
        container.move_down("alpha")
        container.blocks["gamma"].set_content_visible(False)

        assert container.serialise() == f"beta,alpha,{HIDDEN_MARK}gamma"

    def test_apply_state_restores_order_and_visibility(self, qt_application) -> None:  # noqa: ARG001
        """رفت و برگشت کامل باید دقیقاً همان حالت را بدهد."""
        box = ArrangeableContainer(Translator("fa"))
        for key in ("alpha", "beta", "gamma"):
            box.add_block(key, key.upper(), QLabel(key))

        box.apply_state(f"gamma,{HIDDEN_MARK}alpha,beta")

        assert box.order == ["gamma", "alpha", "beta"]
        assert not box.blocks["alpha"].content_visible
        assert box.blocks["beta"].content_visible

    def test_new_blocks_are_appended_not_lost(self, qt_application) -> None:  # noqa: ARG001
        """
        کارت تازه در نسخهٔ بعدی برنامه نباید ناپدید شود.

        چیدمان ذخیره‌شدهٔ کاربر نامش را نمی‌داند، پس باید به انتها برود.
        """
        box = ArrangeableContainer(Translator("fa"))
        for key in ("alpha", "beta", "newcomer"):
            box.add_block(key, key.upper(), QLabel(key))

        box.apply_state("beta,alpha")

        assert box.order == ["beta", "alpha", "newcomer"]
        assert box.blocks["newcomer"].content_visible

    def test_unknown_keys_in_state_are_skipped(self, container) -> None:
        """بخشی که دیگر وجود ندارد نباید خطا بسازد."""
        container.apply_state("gamma,deleted_block,alpha,beta")

        assert container.order == ["gamma", "alpha", "beta"]

    def test_empty_state_leaves_the_default_order(self, container) -> None:
        """نخستین اجرا هیچ چیدمان ذخیره‌شده‌ای ندارد."""
        container.apply_state("")

        assert container.order == ["alpha", "beta", "gamma"]

    def test_duplicate_keys_are_collapsed(self, container) -> None:
        """فایل دستکاری‌شده نباید یک بخش را دوبار درج کند."""
        container.apply_state("beta,beta,alpha,gamma")

        assert container.order == ["beta", "alpha", "gamma"]

    def test_changes_emit_a_saveable_string(self, container) -> None:
        """کنترلر باید بتواند بی‌درنگ ذخیره کند."""
        seen: list[str] = []
        container.layout_changed.connect(seen.append)

        container.move_down("alpha")
        container.blocks["gamma"].set_content_visible(False)

        assert seen[0] == "beta,alpha,gamma"
        assert seen[-1] == f"beta,alpha,{HIDDEN_MARK}gamma"

    def test_reset_restores_defaults(self, container) -> None:
        """بازنشانی باید هم ترتیب و هم نمایانی را برگرداند."""
        container.move_down("alpha")
        container.blocks["beta"].set_content_visible(False)

        container.reset(["alpha", "beta", "gamma"])

        assert container.order == ["alpha", "beta", "gamma"]
        assert all(block.content_visible for block in container.blocks.values())


class TestDashboardIntegration:
    """چیدمان روی صفحهٔ داشبورد واقعی."""

    @pytest.fixture()
    def dashboard(self, qt_application):  # noqa: ARG002 - نیاز به QApplication
        """صفحهٔ داشبورد."""
        from ui.pages.dashboard_page import DashboardPage

        return DashboardPage(Translator("fa"))

    def test_dashboard_sections_are_arrangeable(self, dashboard) -> None:
        """چهار بخش اصلی داشبورد باید جابه‌جاشدنی باشند."""
        from ui.pages.dashboard_page import DEFAULT_BLOCK_ORDER

        assert dashboard.blocks.order == list(DEFAULT_BLOCK_ORDER)

    def test_arrange_bars_hidden_until_requested(self, dashboard) -> None:
        """در حالت عادی، صفحه نباید شلوغ‌تر از قبل شود."""
        dashboard.show()

        assert not any(block.bar.isVisible() for block in dashboard.blocks.blocks.values())

        dashboard.arrange_button.setChecked(True)
        assert all(block.bar.isVisible() for block in dashboard.blocks.blocks.values())

    def test_arrange_button_label_follows_state(self, dashboard) -> None:
        """متن دکمه باید کنش بعدی را نشان دهد."""
        assert dashboard.arrange_button.text() == dashboard.tr_.tr("layout.arrange")

        dashboard.arrange_button.setChecked(True)
        assert dashboard.arrange_button.text() == dashboard.tr_.tr("layout.done")

    def test_dashboard_layout_round_trip(self, dashboard, qt_application) -> None:  # noqa: ARG002
        """چیدمان یک کاربر باید در اجرای بعدی برگردد."""
        from ui.pages.dashboard_page import DashboardPage

        dashboard.blocks.move_up("signals")
        dashboard.blocks.blocks["stats"].set_content_visible(False)
        state = dashboard.layout_state()

        restored = DashboardPage(Translator("fa"))
        restored.apply_layout_state(state)

        assert restored.blocks.order == dashboard.blocks.order
        assert not restored.blocks.blocks["stats"].content_visible

    def test_dashboard_emits_layout_changes(self, dashboard) -> None:
        """تغییر چیدمان باید به کنترلر برسد تا ذخیره شود."""
        seen: list[str] = []
        dashboard.layout_changed.connect(seen.append)

        dashboard.blocks.move_down("ticker")

        assert seen and "ticker" in seen[-1]

    def test_reset_layout_restores_default_order(self, dashboard) -> None:
        """کاربر باید بتواند به حالت اولیه برگردد."""
        from ui.pages.dashboard_page import DEFAULT_BLOCK_ORDER

        dashboard.blocks.move_up("signals")
        dashboard.reset_layout()

        assert dashboard.blocks.order == list(DEFAULT_BLOCK_ORDER)

    def test_layout_preference_key_is_registered(self) -> None:
        """بدون ثبت کلید، چیدمان کاربر ذخیره نمی‌شود."""
        from app.config.defaults import DEFAULT_SETTINGS, SettingKey
        from app.core.auth_service import PREFERENCE_KEYS

        assert SettingKey.UI_DASHBOARD_LAYOUT.value in PREFERENCE_KEYS
        assert DEFAULT_SETTINGS[SettingKey.UI_DASHBOARD_LAYOUT.value] == ""

    def test_locale_keys_exist_for_both_languages(self) -> None:
        """هیچ متنی در کد سفت نشده باشد."""
        for language in ("fa", "en"):
            translator = Translator(language)
            for key in (
                "layout.arrange",
                "layout.done",
                "layout.move_up",
                "layout.move_down",
                "layout.hide",
                "layout.show",
                "layout.saved",
            ):
                assert translator.tr(key) != key
