package lab.maidops.project;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "registered_tasks")
public class RegisteredTaskEntity {
    @Id
    @Column(length = 64)
    private String id;

    @Column(name = "project_id", nullable = false, length = 64)
    private String projectId;

    @Column(nullable = false, length = 120)
    private String name;

    @Column(name = "plan_text", nullable = false, length = 1000)
    private String planText;

    @Column(name = "argv_json", length = 2000)
    private String argvJson;

    @Column(name = "relative_workdir", length = 200)
    private String relativeWorkdir;

    @Column(name = "timeout_seconds")
    private Integer timeoutSeconds;

    public String getId() {
        return id;
    }

    public String getProjectId() {
        return projectId;
    }

    public String getName() {
        return name;
    }

    public String getPlanText() {
        return planText;
    }

    public String getArgvJson() {
        return argvJson;
    }

    public String getRelativeWorkdir() {
        return relativeWorkdir;
    }

    public Integer getTimeoutSeconds() {
        return timeoutSeconds;
    }

    public void setId(String id) {
        this.id = id;
    }

    public void setProjectId(String projectId) {
        this.projectId = projectId;
    }

    public void setName(String name) {
        this.name = name;
    }

    public void setPlanText(String planText) {
        this.planText = planText;
    }

    public void setArgvJson(String argvJson) {
        this.argvJson = argvJson;
    }

    public void setRelativeWorkdir(String relativeWorkdir) {
        this.relativeWorkdir = relativeWorkdir;
    }

    public void setTimeoutSeconds(Integer timeoutSeconds) {
        this.timeoutSeconds = timeoutSeconds;
    }
}
