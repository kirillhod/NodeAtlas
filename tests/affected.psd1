# Test selection for iteration.
#
# `Groups` bundles GUI tests by the feature area they exercise; a test may
# appear in more than one group. `Modules` maps a changed source file to the
# groups that can observe it, so `run_affected.ps1` can turn a diff into a test
# list. Add a new test to at least one group and a new module to `Modules`;
# otherwise `run_matrix.ps1 -Group` cannot select it and `run_affected.ps1`
# falls back to the full tier for an unknown `node_atlas/` module.
#
# The full 33-test tier stays the release check. This file only shortens the
# loop between edits.
@{
    Groups = @{
        core = @(
            'test_export.py',
            'test_large.py',
            'test_limits.py',
            'test_maxmp.py',
            'test_trees.py',
            'test_texture.py',
            'test_legacy.py',
            'test_group.py'
        )
        selected = @(
            'test_selected.py',
            'test_selected_comp.py',
            'test_selected_links.py',
            'test_estimate_selected.py'
        )
        panel = @(
            'test_estimate.py',
            'test_estimate_selected.py',
            'test_preview.py',
            'test_ui_options.py',
            'test_naming.py'
        )
        state = @(
            'test_ui_options.py',
            'test_cancel.py',
            'test_fail.py',
            'test_arealost.py',
            'test_multiarea.py',
            'test_multiwindow.py',
            'test_group.py'
        )
        density = @(
            'test_density.py',
            'test_scaling.py',
            'test_boost.py',
            'test_extreme.py',
            'test_padding.py',
            'test_1000.py'
        )
        io = @(
            'test_naming.py',
            'test_clipboard.py',
            'test_path.py',
            'test_readonly.py',
            'test_diskfull.py',
            'test_limits.py'
        )
        repeat = @(
            'test_repeat.py',
            'test_longlink.py'
        )
    }

    Modules = @{
        'node_atlas/bounds.py' = @('core', 'selected', 'panel', 'density', 'repeat')
        'node_atlas/capture.py' = @('core', 'selected', 'panel', 'density', 'repeat', 'state')
        'node_atlas/operators.py' = @('core', 'selected', 'panel', 'state', 'repeat', 'io')
        'node_atlas/preview.py' = @('panel', 'repeat', 'core')
        'node_atlas/stitch.py' = @('core', 'density', 'repeat', 'io')
        'node_atlas/preferences.py' = @('panel', 'density', 'io')
        'node_atlas/__init__.py' = @('panel', 'state', 'io')
        'node_atlas/log.py' = @()
        'node_atlas/blender_manifest.toml' = @()
    }
}
