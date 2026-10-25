from pathlib import Path

from core.result import Err, Ok
from harness.installation_cleanup import plan_cleanup, rewrite_document
from host_adapters.installation_contract import Component, Inventory


def component(
    kind="hook",
    selector=("hooks", 0),
    path=Path("/tmp/project/settings.json"),
    owned=True,
    scope="user",
):
    return Component(kind, "fake", scope, path, owned=owned, selector=selector)


def test_shared_hook_without_selector_is_never_path_removed():
    assert (
        plan_cleanup(Inventory((component(selector=()),)), "all", purge=True).value
        == ()
    )


def test_shared_settings_and_backup_are_never_whole_file_removed():
    assert (
        plan_cleanup(
            Inventory((component(kind="settings", selector=()),)), "all", purge=True
        ).value
        == ()
    )
    assert (
        plan_cleanup(
            Inventory((component(kind="backup", selector=()),)), "all", purge=True
        ).value
        == ()
    )


def test_settings_selector_is_removed_as_entry():
    result = plan_cleanup(
        Inventory((component(kind="settings", selector=("owned",)),)), "all"
    )
    assert isinstance(result, Ok) and result.value[0].action == "remove_entry"


def test_unowned_component_is_ignored():
    assert (
        plan_cleanup(Inventory((component(owned=False),)), "all", purge=True).value
        == ()
    )


def test_protected_kind_is_ignored_even_when_owned():
    assert (
        plan_cleanup(Inventory((component(kind="auth"),)), "all", purge=True).value
        == ()
    )


def test_local_requires_roots():
    result = plan_cleanup(Inventory(), "local")
    assert isinstance(result, Err) and result.failure.code == "project_roots_required"


def test_all_requires_local_component_inside_explicit_root():
    assert (
        plan_cleanup(
            Inventory((component(scope="local"),)),
            "all",
            projects=(Path("/tmp/other"),),
            purge=True,
        ).value
        == ()
    )


def test_jsonc_comment_removal_preserves_urls_and_hashes():
    result = rewrite_document(
        '{"url":"https://x/#a", // comment\n "owned": 1}', ".jsonc", (("owned",),)
    )
    assert (
        isinstance(result, Ok)
        and "https://x/#a" in result.value
        and "owned" not in result.value
    )


def test_json_selector_missing_is_error():
    result = rewrite_document('{"kept": 1}', ".json", (("missing",),))
    assert isinstance(result, Err) and result.failure.code == "selector_not_found"


def test_json_nested_selector_prunes_empty_parent():
    result = rewrite_document(
        '{"owned":{"entry":1},"kept":2}', ".json", (("owned", "entry"),)
    )
    assert (
        isinstance(result, Ok)
        and "owned" not in result.value
        and "kept" in result.value
    )


def test_json_foreign_empty_containers_are_retained():
    result = rewrite_document(
        '{"foreign": {}, "owned": {"entry": 1}, "items": []}',
        ".json",
        (("owned", "entry"),),
    )
    assert (
        isinstance(result, Ok)
        and '"foreign": {}' in result.value
        and '"items": []' in result.value
    )


def test_toml_quoted_header_is_removed_exactly():
    result = rewrite_document(
        '["mcp.servers"]\ncommand = "owned"\n[kept]\nvalue = 1\n',
        ".toml",
        (("mcp.servers",),),
    )
    assert (
        isinstance(result, Ok)
        and "mcp.servers" not in result.value
        and "[kept]" in result.value
    )


def test_toml_array_tables_are_explicitly_unsupported():
    result = rewrite_document('[[servers]]\nname = "x"\n', ".toml", (("servers",),))
    assert isinstance(result, Err) and result.failure.code == "unsupported_document"


def test_toml_foreign_array_tables_before_and_after_selected_table_are_preserved():
    foreign_before = '[[before]]\nname = "before"\n'
    foreign_after = '[[after]]\nname = "after"\n'
    result = rewrite_document(
        foreign_before
        + "[owned]\nvalue = 1\n[owned.nested]\nvalue = 2\n"
        + foreign_after,
        ".toml",
        (("owned",),),
    )
    assert isinstance(result, Ok) and result.value == foreign_before + foreign_after


def test_toml_managed_block_and_other_owned_table_are_removed_together():
    result = rewrite_document(
        '# BEGIN monolithic-dev-harness\n[hooks]\ncommand = "owned"\n# END monolithic-dev-harness\n'
        '["other"]\nvalue = 1\n[kept]\nvalue = 2\n',
        ".toml",
        (("__managed_block__",), ("other",)),
    )
    assert (
        isinstance(result, Ok)
        and "hooks" not in result.value
        and "other" not in result.value
        and "[kept]" in result.value
    )


def test_toml_managed_kimi_block_is_removed_and_foreign_content_retained():
    result = rewrite_document(
        '# BEGIN monolithic-dev-harness\n[hooks]\ncommand = "owned"\n# END monolithic-dev-harness\n[kept]\nvalue = 1\n',
        ".toml",
        (("__managed_block__",),),
    )
    assert (
        isinstance(result, Ok)
        and "hooks" not in result.value
        and "[kept]" in result.value
    )


def test_invalid_document_is_error():
    result = rewrite_document("{", ".json", (("x",),))
    assert isinstance(result, Err) and result.failure.code == "invalid_document"
