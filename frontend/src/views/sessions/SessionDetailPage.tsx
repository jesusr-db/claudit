import {
  Box,
  Heading,
  HStack,
  Text,
  Spinner,
  Badge,
  VStack,
} from "@chakra-ui/react";
import { useParams } from "react-router-dom";
import { useSessionTimeline } from "@/shared/hooks/useApi";
import { SessionTimeline } from "./components/SessionTimeline";

export default function SessionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, error } = useSessionTimeline(id || "");

  if (!id) return <Text>No session ID</Text>;
  if (isLoading) return <Spinner />;
  if (error) return <Text color="red.500">Failed to load session</Text>;

  const events = data?.events || [];

  return (
    <Box p={6}>
      <VStack align="stretch" spacing={4}>
        <Heading size="lg">Session Timeline</Heading>
        <HStack spacing={4}>
          <Text fontFamily="mono" fontSize="sm">
            {id}
          </Text>
          <Badge>{events.length} events</Badge>
        </HStack>
        <SessionTimeline events={events} />
      </VStack>
    </Box>
  );
}
