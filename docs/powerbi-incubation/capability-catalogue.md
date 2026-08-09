# Power BI UI MCP — Candidate Capability Catalogue

Status values used during live discovery:

```text
SUPPORTED
SUPPORTED_WITH_LIMITS
UNSUPPORTED
BLOCKED_PERMISSION
BLOCKED_LICENSE
BLOCKED_TENANT_POLICY
BLOCKED_AUTH
NOT_ATTESTED
UI_DRIFTED
```

No capability becomes public/live merely because it appears in this catalogue. Promotion requires live tenant evidence and UI contract attestation.

## 1. Session and discovery

```text
powerbi_session_start
powerbi_session_status
powerbi_session_close
powerbi_discover_capabilities
powerbi_current_context
powerbi_capture_state
powerbi_inventory_workspace
```

## 2. Workspaces and content discovery

```text
powerbi_list_workspaces
powerbi_open_workspace
powerbi_list_reports
powerbi_open_report
powerbi_list_dashboards
powerbi_list_semantic_models
powerbi_get_report_metadata
powerbi_get_model_metadata
```

## 3. Report/page operations

```text
powerbi_list_pages
powerbi_open_page
powerbi_create_page
powerbi_duplicate_page
powerbi_rename_page
powerbi_delete_page
powerbi_reorder_page
powerbi_hide_page
powerbi_show_page
powerbi_set_page_size
powerbi_set_page_background
```

## 4. Visual operations

```text
powerbi_list_visuals
powerbi_create_visual
powerbi_duplicate_visual
powerbi_delete_visual
powerbi_change_visual_type
powerbi_move_visual
powerbi_resize_visual
powerbi_align_visuals
powerbi_distribute_visuals
powerbi_set_visual_geometry
powerbi_add_visual_field
powerbi_remove_visual_field
powerbi_set_visual_axis
powerbi_set_visual_legend
powerbi_set_visual_values
powerbi_set_visual_tooltip
powerbi_set_visual_aggregation
powerbi_set_visual_sort
```

## 5. Formatting

```text
powerbi_format_title
powerbi_format_subtitle
powerbi_format_value
powerbi_format_label
powerbi_format_font
powerbi_format_alignment
powerbi_format_background
powerbi_format_border
powerbi_format_shadow
powerbi_format_axis
powerbi_format_legend
powerbi_format_data_labels
powerbi_format_number
powerbi_format_word_wrap
powerbi_format_conditional
powerbi_apply_visual_style
powerbi_copy_visual_format
powerbi_apply_report_theme
```

## 6. Filters, slicers and interactions

```text
powerbi_get_filters
powerbi_filter_visual
powerbi_filter_page
powerbi_filter_report
powerbi_clear_filter
powerbi_reset_filters
powerbi_create_slicer
powerbi_set_slicer_field
powerbi_select_slicer_value
powerbi_clear_slicer
powerbi_get_interactions
powerbi_set_cross_filter
powerbi_set_cross_highlight
powerbi_disable_interaction
```

## 7. Navigation, drill and bookmarks

```text
powerbi_enable_drill
powerbi_configure_drilldown
powerbi_create_drillthrough_page
powerbi_set_drillthrough_field
powerbi_create_navigation_button
powerbi_create_back_button
powerbi_set_button_action
powerbi_list_bookmarks
powerbi_create_bookmark
powerbi_update_bookmark
powerbi_delete_bookmark
powerbi_reorder_bookmarks
powerbi_assign_bookmark_button
```

## 8. Semantic model

Candidate operations depend on what the tenant/account/model exposes through the browser.

```text
powerbi_open_model
powerbi_inspect_model
powerbi_list_tables
powerbi_list_columns
powerbi_list_measures
powerbi_list_relationships
powerbi_create_relationship
powerbi_update_relationship
powerbi_delete_relationship
powerbi_list_roles
powerbi_create_rls_role
powerbi_update_rls_role
powerbi_delete_rls_role
```

## 9. DAX fast path

```text
powerbi_dax_create_measure
powerbi_dax_create_measures_bulk
powerbi_dax_update_measure
powerbi_dax_delete_measure
powerbi_dax_create_column
powerbi_dax_create_table
powerbi_dax_validate
```

## 10. TMDL fast path

```text
powerbi_tmdl_open
powerbi_tmdl_script_existing
powerbi_tmdl_preview
powerbi_tmdl_apply
powerbi_tmdl_apply_bulk
powerbi_tmdl_validate
```

TMDL is treated as an acceleration surface, not an unconditional dependency. The driver must fall back to supported UI operations if TMDL is unavailable.

## 11. Power Query / M fast path

```text
powerbi_query_list
powerbi_query_open
powerbi_query_create
powerbi_query_rename
powerbi_query_duplicate
powerbi_query_open_advanced_editor
powerbi_query_apply_m
powerbi_query_validate
powerbi_query_apply
```

Higher-level query macros may include:

```text
powerbi_query_remove_columns
powerbi_query_change_type
powerbi_query_filter_rows
powerbi_query_replace_values
powerbi_query_merge
powerbi_query_append
powerbi_query_group_by
powerbi_query_pivot
powerbi_query_unpivot
powerbi_query_create_custom_column
```

These can be implemented either semantically through UI steps or by generating/applying M when the Advanced Editor is available.

## 12. Refresh and validation

```text
powerbi_refresh_model
powerbi_get_refresh_state
powerbi_get_refresh_history_ui
powerbi_validate_report
powerbi_validate_page
powerbi_validate_visual
powerbi_validate_model
powerbi_capture_evidence
```

## 13. Dashboards and distribution

Only expose if capability discovery proves the account can perform the corresponding operation.

```text
powerbi_dashboard_create
powerbi_dashboard_rename
powerbi_dashboard_pin_visual
powerbi_dashboard_pin_page
powerbi_tile_move
powerbi_tile_resize
powerbi_tile_rename
powerbi_tile_delete
powerbi_manage_access
powerbi_share_report
powerbi_app_create
powerbi_app_update
powerbi_app_publish
```

## 14. High-level macros

```text
powerbi_create_kpi_card
powerbi_create_management_page
powerbi_create_sprint_dashboard
powerbi_create_executive_summary
powerbi_normalize_report_format
powerbi_align_page
powerbi_fix_overflow
powerbi_fix_long_labels
powerbi_find_inconsistent_visuals
powerbi_build_report_from_spec
```

## 15. Public tool budget

Do not expose every primitive directly to the LLM. Target a compact semantic public surface (approximately 40–60 tools) backed by a larger internal primitive catalogue and deterministic workflow/macro engine.
