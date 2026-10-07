FROM node:22-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install --omit=dev

COPY src ./src
COPY scripts ./scripts

# On ne tourne pas en root (bonne pratique de sécurité)
USER node

EXPOSE 3000
CMD ["node", "src/server.js"]
