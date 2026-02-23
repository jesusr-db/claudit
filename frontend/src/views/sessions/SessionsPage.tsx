import { Box, Heading, VStack, Spinner, Text } from "@chakra-ui/react";
import { useSessions } from "@/shared/hooks/useApi";
import { SessionCard } from "./components/SessionCard";

export default function SessionsPage() {
  const { data, isLoading, error } = useSessions();

  return (
    <Box p={6}>
      <Heading size="lg" mb={6}>
        Sessions
      </Heading>
      {isLoading && <Spinner />}
      {error && <Text color="red.500">Failed to load sessions</Text>}
      <VStack spacing={3} align="stretch">
        {(data?.sessions || []).map((s) => (
          <SessionCard key={s.session_id} session={s} />
        ))}
        {data?.sessions?.length === 0 && (
          <Text color="gray.500">No sessions found</Text>
        )}
      </VStack>
    </Box>
  );
}
