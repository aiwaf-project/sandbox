# AIWAF Full-Stack Sandbox & Testing Guide

This sandbox environment spins up the vulnerable **OWASP Juice Shop** application behind over a dozen different API Gateway / Web Application Firewall proxies powered by `aiwaf`. 

The goal of this sandbox is to prove that AIWAF provides consistent, powerful, framework-agnostic protection regardless of the backend language.

## Available Proxies

The `docker-compose.yml` spins up the following protected proxies:

**Node.js Ecosystem (`aiwaf-js`)**
* `protected_node` (Express) - Port 3000
* `protected_fastify` - Port 3002
* `protected_hapi` - Port 3003
* `protected_koa` - Port 3004
* `protected_nest` - Port 3005
* `protected_next` - Port 3006
* `protected_adonis` - Port 3007
* `protected_sails` - Port 3008

**Python Ecosystem (`aiwaf-py`)**
* `protected_django` - Port 3009
* `protected_flask` - Port 3010
* `protected_fastapi` - Port 3011

**PHP / Java Ecosystems (`aiwaf-php`, `aiwaf-java`)**
* `protected_laravel` - Port 8081
* `protected_symfony` - Port 8082
* `protected_wordpress` - Port 8083
* `protected_java` - Port 8080
* `protected_spring` - Port 8084

*And the unprotected baseline:*
* `direct` (Juice Shop directly) - Port 3001

---

## 🚀 Running the Sandbox

To build and start all proxies and the Juice Shop backend, run:

```bash
docker compose up -d --build
```

---

## 🛡️ The Attack Suite (`attack-suite.py`)

We have built a unified Python attack script (`attack-suite.py`) that simulates malicious traffic against any of the targets. It heavily utilizes the **OWASP Web Security Testing Guide (WSTG) v4.2** to test the WAF's capabilities.

### What AIWAF Tests For (OWASP WSTG v4.2 Coverage)

The suite executes the following specific probes to verify AIWAF's defenses:

1. **Information Gathering & Configuration (WSTG-CONF)**
   * `wstg_conf_05`: Admin Interface Probing (tests for `/admin`, `/administrator/`, `/config`).
   * `wstg_conf_06`: HTTP Method Tampering (tests for `TRACE`, `OPTIONS`, `TRACK`).
2. **Authentication Testing (WSTG-ATHN)**
   * `brute_force` & `credential_stuffing`: Rapid login attempts to test Rate Limiting & Flood protection.
   * `wstg_athn_02`: Default Credential usage testing.
   * `wstg_athn_04`: Authentication Bypass via SQLi (e.g. `' OR 1=1 --`).
3. **Authorization Testing (WSTG-ATHZ)**
   * `wstg_athz_01`: Directory Traversal (e.g. `../../etc/passwd`).
4. **Input Validation Testing (WSTG-INPV)**
   * `wstg_inpv_01_02`: Cross-Site Scripting (XSS) via query parameters and paths.
   * `wstg_inpv_04`: HTTP Parameter Pollution (sending multiple `?id=1&id=2`).
   * `wstg_inpv_05`: Advanced SQL Injection (Boolean, UNION, Time-based).
   * `wstg_inpv_07`: XML External Entity (XXE) Injection.
   * `wstg_inpv_11`: Local File Inclusion (LFI) via PHP filters (`php://filter`).
   * `wstg_inpv_12`: OS Command Injection (e.g. `| id`, `; cat /etc/passwd`).
5. **Error Handling (WSTG-ERRH)**
   * `wstg_errh_01`: Sending malformed JSON to trigger backend stack traces.
6. **Identity Management (WSTG-IDNT)**
   * `wstg_idnt_04`: Account Enumeration probing.

### How to Run the Tests

**1. Test a single target:**
If you want to test how the default Node proxy handles attacks:
```bash
python attack-suite.py http://localhost:3000 protected_node --mode attacks
```
*(This generates a JSON file with the results in the current directory).*

**2. Run the Comprehensive Comparison Matrix:**
To send normal traffic AND attack traffic to **every single framework** and generate a massive JSON comparison matrix:
```bash
python attack-suite.py
```

### Analyzing the Results
Open the generated `comparison_modes_...json` or `results_...json`.
* **Direct Target**: You will see `"blocked": 0` and Status `200` or `500` for attacks, meaning Juice Shop processed the malicious payload.
* **Protected Targets**: You should see `"blocked": <number>` and Status `403` or `429` for almost all attacks, proving the AIWAF middleware intercepted the threat at the application edge!

## Cleanup
```bash
docker compose down
rm *.json
```
