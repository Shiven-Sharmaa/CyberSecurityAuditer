#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "chunker.h"
#include "bm25.h"
namespace py = pybind11;

static Index g_index;
static std::vector<Chunk> g_chunks;

PYBIND11_MODULE(nciipc_cpp, m) {
    m.def("build_index", [](std::vector<std::string> texts) {
        g_chunks.clear();
        for (int i = 0; i < (int)texts.size(); i++) {
            auto c = chunk_document(i, texts[i]);
            g_chunks.insert(g_chunks.end(), c.begin(), c.end());
        }
        g_index = Index{};
        build_index(g_index, g_chunks);
    });
    m.def("query_bm25", [](std::string q, int k) {
        return query_bm25(g_index, q, k);
    }, py::arg("q"), py::arg("k")=50);
    m.def("get_chunk_text", [](int cid) -> std::string {
        if (cid < 0 || cid >= (int)g_chunks.size()) return "";
        return g_chunks[cid].text;
    });
    m.def("get_chunk_count", []{ return (int)g_chunks.size(); });
    m.def("save_index", [](std::string p){ save_index(g_index, p); });
}