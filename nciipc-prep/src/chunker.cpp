#include "chunker.h"
#include <sstream>
#include <algorithm>
using namespace std;

vector<string> tokenize(const string& text) {
    istringstream ss(text);
    vector<string> tokens;
    string tok;
    while (ss >> tok) tokens.push_back(tok);
    return tokens;
}

vector<Chunk> chunk_document(int doc_id, const string& text,
                                   int window, int stride) {
    auto tokens = tokenize(text);
    vector<Chunk> chunks;
    int n = (int)tokens.size();
    if (n == 0) return chunks;
    int idx = 0;
    for (int start = 0; start < n; start += stride) {
        int end = min(start + window, n);
        string t;
        for (int i = start; i < end; i++) {
            if (i > start) t += ' ';
            t += tokens[i];
        }
        chunks.push_back({doc_id, idx++, start, end, t});
        if (end == n) break;
    }
    return chunks;
}