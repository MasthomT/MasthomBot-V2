class PostgresCursorWrapper:
    def __init__(self, conn):
        self.conn = conn
        self._results = []

    async def execute(self, query: str, args: tuple = None):
        # 1. Traduction automatique des "?" (façon SQLite) en "$1, $2..." (façon PostgreSQL)
        if args:
            parts = query.split('?')
            new_query = parts[0]
            for i in range(1, len(parts)):
                new_query += f"${i}" + parts[i]
            query = new_query

        # 2. Normalisation des horloges (SQLite -> PostgreSQL)
        query = query.replace("datetime('now')", "NOW()").replace("CURRENT_TIMESTAMP", "NOW()")

        # 3. Exécution intelligente (Lecture vs Écriture)
        q_upper = query.strip().upper()
        if q_upper.startswith("SELECT") or q_upper.startswith("WITH") or "RETURNING" in q_upper:
            if args:
                self._results = await self.conn.fetch(query, *args)
            else:
                self._results = await self.conn.fetch(query)
        else:
            if args:
                await self.conn.execute(query, *args)
            else:
                await self.conn.execute(query)
            self._results = []
        
        return self

    async def fetchone(self):
        """Récupère un seul résultat."""
        if self._results and len(self._results) > 0:
            return self._results[0]
        return None

    async def fetchall(self):
        """Récupère tous les résultats."""
        return self._results if self._results else []
