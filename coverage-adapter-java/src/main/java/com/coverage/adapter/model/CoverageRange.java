package com.coverage.adapter.model;

public class CoverageRange {
    private String filePath;
    private int startLine;
    private int startCol;
    private int endLine;
    private int endCol;
    private int statements;
    private int hit;

    public CoverageRange(String filePath, int startLine, int startCol, int endLine, int endCol, int statements, int hit) {
        this.filePath = filePath;
        this.startLine = startLine;
        this.startCol = startCol;
        this.endLine = endLine;
        this.endCol = endCol;
        this.statements = statements;
        this.hit = hit;
    }

    public String getFilePath() {
        return filePath;
    }

    public void setFilePath(String filePath) {
        this.filePath = filePath;
    }

    public int getStartLine() {
        return startLine;
    }

    public void setStartLine(int startLine) {
        this.startLine = startLine;
    }

    public int getStartCol() {
        return startCol;
    }

    public void setStartCol(int startCol) {
        this.startCol = startCol;
    }

    public int getEndLine() {
        return endLine;
    }

    public void setEndLine(int endLine) {
        this.endLine = endLine;
    }

    public int getEndCol() {
        return endCol;
    }

    public void setEndCol(int endCol) {
        this.endCol = endCol;
    }

    public int getStatements() {
        return statements;
    }

    public void setStatements(int statements) {
        this.statements = statements;
    }

    public int getHit() {
        return hit;
    }

    public void setHit(int hit) {
        this.hit = hit;
    }
}

