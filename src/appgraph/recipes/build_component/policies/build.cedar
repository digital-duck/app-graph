// build.cedar: may this build write generated files into output_dir, and run the component's tests?
// write_ok: output_dir is absolute and under the user's home or the temporary folder (appgraph.build.steps.write_root_ok;
// more roots in APPGRAPH_WRITE_ROOTS). The tests run in a container with no network either way (vue_typescript: an
// image per lockfile, built with the network from the scaffold's package files only; appgraph/build/node_image.py).
permit (
    principal == Service::"app-graph",
    action == Action::"build_component",
    resource
) when { context.write_ok && ["python_fastapi", "python_library", "curriculum", "vue_typescript"].contains(context.profile) };
