package ua.tumakha.yuriy.xmpp.light.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.Id;
import jakarta.validation.constraints.Size;

/**
 * @author Yuriy Tumakha.
 */
@Entity(name = "user")
public class User {

    @Id
    @GeneratedValue
    private Long id;

    @Size(min = 2, max = 20)
    @Column(unique = true, nullable = false)
    private String username;

    @Column(nullable = false, length = 1024)
    private String password;

    @Column(nullable = false, columnDefinition = "tinyint(1) default 0")
    private boolean admin;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getPassword() {
        return password;
    }

    public void setPassword(String password) {
        this.password = password;
    }

    public boolean isAdmin() {
        return admin;
    }

    public void setAdmin(boolean admin) {
        this.admin = admin;
    }

}
