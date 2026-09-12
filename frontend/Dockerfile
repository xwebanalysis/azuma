FROM node:24

WORKDIR /app

COPY package*.json ./

RUN npm ci || npm install

COPY . .

EXPOSE 4230

CMD ["npm", "start"]
