# Visual Flow Diagrams & Architecture

## Issue 1: Login Error - Root Cause & Fix

### BEFORE (Broken)
```
User Login Flow:
  1. AuthPage onAuth(user)
     ↓
  2. SheetAgentPage: setUser(user)
     ↓
  3. Render LeftSidebar with:
     - files={files}
     - activeId={activeFileId}
     - onSelect={setActiveFileId}
     - onNewChat={handleNewChat}
     - open={sidebarOpen}
     - onToggle={() => setSidebarOpen((o) => !o)}
     
     ⚠️ MISSING:
     - recentChats ❌
     - onSelectChat ❌
     - activeChatId ❌
     
  4. LeftSidebar tries to access:
     ```typescript
     {recentChats.length === 0 && files.length === 0 ? (
       <div>...</div>
     ) : (
       <ul className="space-y-0.5">
         {recentChats.length > 0 && (  // recentChats is undefined!
           <>
             <li>Recent chats</li>
             {recentChats.map(...)}  // TypeError: t is undefined
           </>
         )}
     ```
     
  5. CRASH: TypeError: can't access property "length", t is undefined
```

### AFTER (Fixed)
```
User Login Flow:
  1. AuthPage onAuth(user)
     ↓
  2. SheetAgentPage: setUser(user)
     ↓
  3. useEffect triggered (user changed)
     ↓
  4. fetchChatHistory(token)
     ↓
  5. Backend: GET /api/chat/history
     → SELECT * FROM chat_sessions WHERE user_id = current_user.id
     → Return [ChatSession, ChatSession, ...]
     ↓
  6. setRecentChats(sessions)
     ↓
  7. Render LeftSidebar with:
     - files={files}
     - recentChats={recentChats} ✓
     - activeId={activeFileId}
     - activeChatId={activeChatId} ✓
     - onSelect={setActiveFileId}
     - onSelectChat={handleSelectChat} ✓
     - onNewChat={handleNewChat}
     - open={sidebarOpen}
     - onToggle={() => setSidebarOpen((o) => !o)}
     ↓
  8. LeftSidebar renders without errors
     Shows: "Recent chats" section with user's sessions
```

---

## Issue 2: Secure Chat History - Architecture

### Database Layer
```
users TABLE (existing)
┌─────────────────────┐
│ id (PK)             │
│ email               │
│ full_name           │
│ hashed_pw           │
│ created_at          │
└─────────────────────┘
        │
        │ ForeignKey
        ↓
chat_sessions TABLE (new)
┌──────────────────────────────┐
│ id (PK)                      │
│ user_id (FK) [indexed]       │ ← Links to users.id
│ title                        │
│ message_count                │
│ created_at                   │
│ updated_at                   │
└──────────────────────────────┘

Query Pattern (Secure):
  SELECT * FROM chat_sessions
  WHERE user_id = '12345-current-user'
  ORDER BY created_at DESC;
  
  → Returns ONLY this user's chats
  → Never exposes other users' data
  → Foreign key prevents orphaned records
```

### Authentication Flow
```
Frontend (React)
  │
  ├─→ User Login
  │   └─→ POST /api/auth/login
  │       → JWT Token + User {id, email, full_name}
  │
  ├─→ Store Token: localStorage.setItem("token", token)
  │
  ├─→ useEffect(dependency: [user])
  │   └─→ fetchChatHistory(token)
  │       └─→ GET /api/chat/history
  │           Header: Authorization: Bearer <token>
  │
  └─→ Backend (FastAPI)
      │
      ├─→ Route: GET /api/chat/history
      │   ├─→ Decode JWT token
      │   ├─→ Extract user_id from token
      │   ├─→ Query: WHERE user_id = <extracted user_id>
      │   └─→ Return: ChatSessionOut[]
      │
      └─→ Database (SQLite)
          └─→ SELECT * FROM chat_sessions
              WHERE user_id = ?
              ORDER BY created_at DESC
```

### Data Flow Diagram
```
┌─────────────────────────────────────────────────────┐
│                     USER LOGIN                      │
└─────────────────────────────────────────────────────┘
                          │
                          ↓
┌─────────────────────────────────────────────────────┐
│  Frontend: setUser(u), then useEffect triggers     │
│  fetchChatHistory(getToken())                       │
└─────────────────────────────────────────────────────┘
                          │
                          ↓
┌─────────────────────────────────────────────────────┐
│  Backend GET /api/chat/history                     │
│  Verify token: user_id = "abc123"                  │
│  Query: SELECT * WHERE user_id = "abc123"          │
└─────────────────────────────────────────────────────┘
                          │
                          ↓
┌─────────────────────────────────────────────────────┐
│  Return: [                                          │
│    { id: "chat-1", title: "...", created_at: ... },│
│    { id: "chat-2", title: "...", created_at: ... } │
│  ]                                                  │
└─────────────────────────────────────────────────────┘
                          │
                          ↓
┌─────────────────────────────────────────────────────┐
│  Frontend: setRecentChats(sessions)                │
│  LeftSidebar renders "Recent chats" with sessions  │
└─────────────────────────────────────────────────────┘
```

---

## User Isolation Guarantee

### Scenario: Two Users Login

```
User A (id: "user-a-123")
│
├─→ Login
├─→ fetchChatHistory(tokenA)
│   └─→ Backend queries WHERE user_id = "user-a-123"
│       └─→ Returns: [Chat-A-1, Chat-A-2]
├─→ setRecentChats([Chat-A-1, Chat-A-2])
└─→ LeftSidebar shows: Chat-A-1, Chat-A-2

                ↕ Different browser/tab ↕

User B (id: "user-b-456")
│
├─→ Login
├─→ fetchChatHistory(tokenB)
│   └─→ Backend queries WHERE user_id = "user-b-456"
│       └─→ Returns: [Chat-B-1]
├─→ setRecentChats([Chat-B-1])
└─→ LeftSidebar shows: Chat-B-1

🔒 USER ISOLATION GUARANTEES:
  ✓ User A cannot query User B's WHERE clause
  ✓ User B cannot query User A's WHERE clause
  ✓ No shared state between users
  ✓ Each user's token only decodes to their own user_id
  ✓ Database FK prevents direct access to other user's rows
```

---

## New Chat Session Creation Flow

```
User sends message:
  1. Input: "Hello, can you help?"
     ↓
  2. Frontend: sendMessage(text, sessionId=null)
     POST /api/chat/
     Body: {message: "Hello...", session_id: null}
     ↓
  3. Backend: chat() endpoint
     - Gets response from agent
     - Checks: current_user exists AND !body.session_id
     - If true:
         session = ChatSession(
           id=uuid(),
           user_id=current_user.id,
           title="Hello, can you help?",
           message_count="1"
         )
         db.add(session)
         db.commit()
     ↓
  4. Return response with session_id
     ↓
  5. Frontend: Receives response with new session_id
     ↓
  6. Browser storage: sessionIdRef.current = new_session_id
     ↓
  7. Next message uses: sessionIdRef.current (existing session)
     ↓
  8. User logs out and back in
     ↓
  9. fetchChatHistory() runs
     Query: WHERE user_id = current_user.id
     ↓
  10. Previous chat appears in LeftSidebar! ✓
```

---

## Security Checklist

```
AUTHENTICATION
  ☑ JWT token required for /api/chat/history
  ☑ Token validated before querying
  ☑ Invalid token returns 401 Unauthorized
  ☑ Token expiry handled gracefully

AUTHORIZATION  
  ☑ user_id extracted from token
  ☑ WHERE user_id = current_user.id enforced
  ☑ No way to query other user_ids
  ☑ Query always filtered at DB level

DATA ISOLATION
  ☑ Foreign key prevents orphaned records
  ☑ Cascade delete on user deletion
  ☑ No cross-user data leakage
  ☑ Each user sees ONLY their own sessions

IMPLEMENTATION
  ☑ Backend: strict WHERE clause
  ☑ Frontend: token passed in header
  ☑ No plain-text passwords
  ☑ HTTPS recommended for production
```

---

## Integration Points

```
┌─────────────────────────────────────────────────────┐
│              FRONTEND (React)                       │
├─────────────────────────────────────────────────────┤
│ routes/index.tsx                                    │
│  └─ auth.ts: getToken(), getSavedUser()           │
│  └─ sheet-agent.ts: fetchChatHistory()            │
│  └─ LeftSidebar: {recentChats, onSelectChat}      │
└─────────────────────────────────────────────────────┘
           ↕ REST API + JWT
┌─────────────────────────────────────────────────────┐
│              BACKEND (FastAPI)                      │
├─────────────────────────────────────────────────────┤
│ auth.py                                             │
│  └─ _current_user: decodes JWT, returns User       │
│ chat.py                                             │
│  └─ POST /api/chat/: saves new ChatSession         │
│  └─ GET /api/chat/history: returns user's chats    │
└─────────────────────────────────────────────────────┘
           ↕ SQLAlchemy ORM
┌─────────────────────────────────────────────────────┐
│           DATABASE (SQLite)                         │
├─────────────────────────────────────────────────────┤
│ users table                                         │
│ chat_sessions table (new)                           │
│  └─ Foreign key: user_id → users.id                │
└─────────────────────────────────────────────────────┘
```

---

## Deployment Timeline

```
Time  Action                          Verification
────  ──────────────────────────────  ────────────────────────
T0    Backup current database         ✓ Backup successful
      
T+1m  Create chat_sessions table      ✓ Table exists
      Run migration script             ✓ No errors
      
T+2m  Restart backend                 ✓ Service up
      Verify endpoints                ✓ /api/chat/history returns 200
      
T+3m  Rebuild frontend                ✓ Build succeeds
      npm run build                    ✓ No TS errors
      
T+5m  Deploy frontend                 ✓ Files served
      Clear browser cache             ✓ Fresh JS loaded
      
T+10m Smoke test                      
      - Create account                ✓ No JS errors
      - Login                         ✓ LeftSidebar renders
      - Send message                  ✓ Chat appears in sidebar
      - Logout/Login                  ✓ Chat persists
      - Test with 2nd user            ✓ User isolation works
      
T+15m PRODUCTION READY                ✓ All checks passed
```
