load("@rules_python//python:defs.bzl", "py_binary", "py_library")

package(default_visibility = ["//visibility:public"])

# Streamlit UI library
py_library(
    name = "streamlit_app",
    srcs = ["proto/app.py"],
# No deps needed - using system packages
)

# Streamlit UI binary with wrapper
py_binary(
    name = "app",
    srcs = ["streamlit_wrapper.py"],
    main = "streamlit_wrapper.py",
    deps = [":streamlit_app"],
    data = ["proto/app.py"],
)