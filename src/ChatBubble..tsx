import React from 'react';
import styled from 'styled-components';

interface ChatBubbleProps {
  text: string;
  time: string;
}

const Bubble = styled.div`
  display: flex;
  align-items: flex-start;
  margin: 10px;
  background-color: #6C63FF;  /* Default color */
  border-radius: 20px;
  padding: 10px;
  max-width: 60%;
  margin-left: auto;
`;

const Text = styled.div`
  color: #fff;
  font-size: 16px;
`;

const Time = styled.div`
  color: #aaa;
  font-size: 12px;
  margin-left: 10px;
`;

const ChatBubble: React.FC<ChatBubbleProps> = ({ text, time }) => (
  <Bubble>
    <Text>{text}</Text>
    <Time>{time}</Time>
  </Bubble>
);

export default ChatBubble;
