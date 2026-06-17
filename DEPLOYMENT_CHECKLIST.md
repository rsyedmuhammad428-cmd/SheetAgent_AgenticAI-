# Integration Testing Checklist

## Pre-Deployment Verification

### Backend Changes
- [x] Database schema updated with `ChatSession` table
- [x] Foreign key constraint added: `user_id` → `users.id`
- [x] Chat.py routes updated with new endpoints
- [x] Authentication dependency injection prepared
- [x] Python syntax validation passed

### Frontend Changes
- [x] ChatSession interface added to sheet-agent.ts
- [x] fetchChatHistory() function added and exported
- [x] LeftSidebar receives all required props (no undefined props)
- [x] useEffect hook for loading chat history added
- [x] handleSelectChat function implemented
- [x] recentChats state properly managed
- [x] TypeScript syntax validation passed

### Login Flow
**Before (BROKEN):**
1. User logs in
2. LeftSidebar renders with missing props
3. JavaScript error: "TypeError: can't access property "length", t is undefined"
4. App crashes

**After (FIXED):**
1. User logs in → AuthPage → index.tsx
2. User state set → recentChats state initialized as []
3. useEffect triggers → fetchChatHistory() called
4. Backend returns user's private chat sessions
5. LeftSidebar renders with valid props
6. "Recent chats" section displays user's sessions
7. User can click to load historical chat
8. No errors

---

## Deployment Steps

### Step 1: Database Migration
```bash
# Create chat_sessions table in SQLite
cd backend
python -c "
from app.models.database import init_db, engine, ChatSession
import asyncio
asyncio.run(init_db())
print('✓ Database migration complete')
"
```

### Step 2: Restart Backend
```bash
docker-compose restart backend
# Wait for backend to be ready (check logs)
docker-compose logs -f backend | grep "Application startup complete"
```

### Step 3: Test Backend Endpoints
```bash
# Test 1: Login and get token
TOKEN=$(curl -s -X POST http://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}' \
  | jq -r .access_token)

# Test 2: Fetch chat history (should be empty for new user)
curl -s -X GET http://localhost/api/chat/history \
  -H "Authorization: Bearer $TOKEN" | jq .

# Test 3: Send message (should create new session)
curl -s -X POST http://localhost/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello"}' | jq .

# Test 4: Fetch history again (should show new session)
curl -s -X GET http://localhost/api/chat/history \
  -H "Authorization: Bearer $TOKEN" | jq .
```

### Step 4: Rebuild & Deploy Frontend
```bash
cd frontend
npm install
npm run build
# Verify build succeeds without errors
ls dist/
```

### Step 5: Verify Frontend App
1. Clear browser cache
2. Open http://localhost
3. Click "Create Account"
4. Enter test credentials
5. **VERIFY:** App loads without JavaScript errors
6. **VERIFY:** LeftSidebar shows "Recent chats" section (empty initially)
7. Send a message
8. **VERIFY:** Message sent successfully
9. **VERIFY:** After response, chat session appears in LeftSidebar
10. Logout and login with same user
11. **VERIFY:** Previous chat appears in LeftSidebar
12. Create second account
13. **VERIFY:** Second account does NOT see first account's chats

---

## Common Issues & Solutions

### Issue: "Cannot find module 'ChatSession'"
**Solution:** Verify import in routes/index.tsx includes `type ChatSession`

### Issue: "TypeError: Can't read property 'forEach' of undefined"
**Solution:** Initialize `recentChats: ChatSession[] = []` in useState

### Issue: "Cannot read property 'length' of undefined"
**Solution:** Always pass `recentChats` prop to LeftSidebar - check line 340+

### Issue: "401 Unauthorized" on /api/chat/history
**Solution:** Verify token is passed in Authorization header with "Bearer " prefix

### Issue: "FOREIGN KEY constraint failed"
**Solution:** Ensure `users` table exists before `chat_sessions` table creation

---

## Rollback Plan

If issues occur, rollback by:

1. Restore previous database backup (if any)
2. Revert backend code:
   ```bash
   git checkout backend/app/models/database.py
   git checkout backend/app/api/routes/chat.py
   docker-compose restart backend
   ```
3. Revert frontend code:
   ```bash
   git checkout frontend/src/lib/sheet-agent.ts
   git checkout frontend/src/routes/index.tsx
   npm run build
   ```

---

## Success Criteria

✅ Login page loads without JavaScript errors  
✅ User can login and see their chat history  
✅ Chat history is user-specific (multi-tenant isolation works)  
✅ New chats appear in sidebar after message sent  
✅ Clicking sidebar chat loads that session  
✅ Logout clears chat history from UI  
✅ No console errors in browser DevTools  
✅ Backend GET /api/chat/history returns only current user's chats  
✅ Performance: Chat history loads within 2 seconds  
✅ Database foreign key constraint prevents orphaned sessions  
