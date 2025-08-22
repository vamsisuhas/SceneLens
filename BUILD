load("@rules_python//python:defs.bzl", "py_binary", "py_library")

package(default_visibility = ["//visibility:public"])

# Master pipeline runner - coordinates all pipeline steps
py_binary(
    name = "pipeline",
    srcs = ["run_pipeline.py"],
    main = "run_pipeline.py",
    deps = ["//pipeline:core"],
)

# API server - simple direct approach
py_binary(
    name = "api",
    srcs = ["//backend:app.py"],
    main = "//backend:app.py",
    deps = ["//backend:api"],
)

# UI application - depends on UI components
py_binary(
    name = "ui",
    srcs = ["//ui:proto/app.py"],
    main = "//ui:proto/app.py", 
    deps = ["//ui:streamlit_app"],
)

# Complete SceneLens application - all components together
py_library(
    name = "scenelens",
    deps = [
        "//pipeline:core",
        "//backend:api", 
        "//ui:streamlit_app",
    ],
)