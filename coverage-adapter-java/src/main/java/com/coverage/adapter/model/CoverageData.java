package com.coverage.adapter.model;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class CoverageData {
    private Map<String, List<CoverageRange>> fileRanges;

    public CoverageData() {
        this.fileRanges = new HashMap<>();
    }

    public CoverageData(Map<String, List<CoverageRange>> fileRanges) {
        this.fileRanges = fileRanges;
    }

    public Map<String, List<CoverageRange>> getFileRanges() {
        return fileRanges;
    }

    public void setFileRanges(Map<String, List<CoverageRange>> fileRanges) {
        this.fileRanges = fileRanges;
    }
}

