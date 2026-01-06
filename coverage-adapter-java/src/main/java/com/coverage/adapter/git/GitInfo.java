package com.coverage.adapter.git;

public class GitInfo {
    private String repo;
    private String repoId;
    private String branch;
    private String commit;
    private String ciProvider;
    private String ciPipelineId;
    private String ciJobId;

    public GitInfo() {
        this.repo = "";
        this.repoId = "";
        this.branch = "";
        this.commit = "";
        this.ciProvider = "";
        this.ciPipelineId = "";
        this.ciJobId = "";
    }

    public String getRepo() {
        return repo;
    }

    public void setRepo(String repo) {
        this.repo = repo;
    }

    public String getRepoId() {
        return repoId;
    }

    public void setRepoId(String repoId) {
        this.repoId = repoId;
    }

    public String getBranch() {
        return branch;
    }

    public void setBranch(String branch) {
        this.branch = branch;
    }

    public String getCommit() {
        return commit;
    }

    public void setCommit(String commit) {
        this.commit = commit;
    }

    public String getCiProvider() {
        return ciProvider;
    }

    public void setCiProvider(String ciProvider) {
        this.ciProvider = ciProvider;
    }

    public String getCiPipelineId() {
        return ciPipelineId;
    }

    public void setCiPipelineId(String ciPipelineId) {
        this.ciPipelineId = ciPipelineId;
    }

    public String getCiJobId() {
        return ciJobId;
    }

    public void setCiJobId(String ciJobId) {
        this.ciJobId = ciJobId;
    }
}

