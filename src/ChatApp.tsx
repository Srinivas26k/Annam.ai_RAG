import React, { useState } from 'react';
import styled from 'styled-components';
import ChatBubble from './ChatBubble.';

const Container = styled.div`
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100%;
  background-color:rgb(244, 237, 237);
`;

const Header = styled.div`
  background-color: #6c63ff;
  padding: 20px;
  color: white;
  font-size: 18px;
  font-weight: bold;
  text-align: center;
`;

const ChatArea = styled.div`
  flex-grow: 1;
  overflow-y: scroll;
  padding: 20px;
  display: flex;
  flex-direction: column;
`;

const InputArea = styled.div`
  display: flex;
  padding: 10px;
  background-color: #fff;
`;

const InputField = styled.input`
  flex-grow: 1;
  padding: 10px;
  font-size: 16px;
  border: 1px solid #ccc;
  border-radius: 20px;
`;

const SendButton = styled.button`
  background-color: #6c63ff;
  color: white;
  border: none;
  padding: 10px;
  border-radius: 50%;
  margin-left: 10px;
  cursor: pointer;
`;

const ChatApp: React.FC = () => {
  const [messages, setMessages] = useState<{ text: string; time: string }[]>([]);
  const [userInput, setUserInput] = useState('');

  const handleSend = () => {
    const userMessage = {
      text: userInput,
      time: new Date().toLocaleTimeString(),
    };

    const botMessage = {
      text: 'We accept most major credit cards, and Paypal',
      time: new Date().toLocaleTimeString(),
    };

    setMessages([...messages, userMessage, botMessage]);
    setUserInput('');
  };

  return (
    <Container>
      <Header>Annam.AI</Header>
      <ChatArea>
        {messages.map((msg, index) => (
          <ChatBubble key={index} text={msg.text} time={msg.time} />
        ))}
      </ChatArea>
      <InputArea>
        <InputField
          type="text"
          value={userInput}
          onChange={(e) => setUserInput(e.target.value)}
          placeholder="Type text"
        />
        <SendButton onClick={handleSend}>Send</SendButton>
      </InputArea>
    </Container>
  );
};

export default ChatApp;
