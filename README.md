### Recent Updates

- Enhanced property selection logic to prioritize properties based on merit.  
- Fixed email template selection to ensure correct templates are applied.  
- Updated automation to dynamically replace `[number]` with the selected number of properties.  
- Improved handling of background issues: skips selection if the value is `"None"`.  
- Implemented robust crash handling to prevent unfinished threads from affecting new tasks.  
- Ensured that any task failure closes the specific task cleanly, preparing the system for subsequent executions.

---

### Issues Identified in the Current RPA Implementation

During testing of the current RPA system, several architectural and stability issues were identified that could impact reliability, scalability, and concurrent task handling.

#### 1. Shared `client.json` File for Data Storage

The automation currently relies on a shared `client.json` file to store client-specific data, which each RPA execution reads instead of receiving parameters directly.  

**Issues:**

- When a new RPA task starts, it overwrites the data in `client.json`.  
- If another RPA task is already running, its required data may be replaced by the new request.  
- Concurrent executions can therefore corrupt each other’s data, leading to incorrect results.

**Recommended Improvement:**

- Pass client-specific data directly to the RPA process (e.g., via API parameters, task queues, or isolated execution contexts) instead of using a shared file.  

---

#### 2. Lack of Proper Session Cleanup After Failures

Testing revealed that when an RPA execution crashes, the session is not properly terminated.  

**Issues:**

- Previous incomplete sessions remain active.  
- New RPA requests attempt to run while the prior session still occupies resources.  
- This can cause freezes or repeated crashes.

**Recommended Improvement:**

- Implement proper session management to include:  
  - Guaranteed cleanup of resources after crashes  
  - Timeout handling for stuck sessions  
  - Isolation of tasks in separate execution environments  

---

#### 3. Blocking Execution Due to `time.sleep()`

The current implementation relies heavily on `time.sleep()` for waiting.  

**Issues:**

- Blocking waits cause the entire process to pause, leaving server resources idle but locked.  
- Multiple concurrent RPA tasks cannot proceed efficiently.  
- This approach reduces scalability and performance in multi-task environments.

**Recommended Improvement:**

- Replace blocking waits with more efficient methods, such as:  
  - Event-driven waiting  
  - Asynchronous task handling  
  - Non-blocking wait mechanisms  
  - Framework-native waiting methods (e.g., Playwright or Selenium wait conditions)  